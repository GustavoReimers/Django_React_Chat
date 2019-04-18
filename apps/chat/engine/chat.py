from channels import Group, DEFAULT_CHANNEL_LAYER, channel_layers
from chat.models import Message, Room, User
from django.db.models import Q

from . import constants
from .base import ActionEngine
from .utils import timestamp


class ChatEngine(ActionEngine):
    def get_control_channel(self, user=None):
        # Current control channel name, unless told to return `user`'s
        # control channel
        if user is None:
            user = self.message.channel_session['user']
        return 'control.{0}'.format(user)

    def get_room_channel(self, room_id):
        return 'room.{0}'.format(room_id)

    def disconnect(self):
        # Discard the channel from the control group
        Group(self.get_control_channel()).discard(
            self.message.reply_channel
        )

        username = self.message.channel_session.get('user')
        if username:
            user = User.objects.get(username=username)

            # Discard the channel from the all the room groups
            for room in Room.objects.filter(users=user):
                Group(self.get_room_channel(room.id)).discard(
                    self.message.reply_channel
                )
            # TODO Set rooms to inactive

    def LOGIN(self, action):
        # Get or create user and assign to session for future requests
        # WARNING: There is NO AUTHENTICATION. Consider moving up to ws_add
        username = action['user']
        user, user_created = User.objects.get_or_create(username=username)
        self.message.channel_session['user'] = username

        # Add this websocket to the user's control channel group
        control = self.get_control_channel()
        self.add(control)

        # Echo back the LOGIN to the client
        self.send({
            'type': constants.LOGIN_SUCCESS,
            'user': username
        })

        # Get or create the list of available rooms
        # Right now each Room is a 1-1 direct message room, but could easily
        # be extended to allow group message rooms.
        # WARNING: This is a very dumb and inefficient first-pass approach,
        # in which we pre-create a Room for every User-User pair. We should
        # instead create rooms on demand or when a user "adds" another user
        # to her "friend list"
        if user_created:
            rooms = []
            for other_user in User.objects.exclude(id=user.id):
                room = Room.objects.create()
                room.users = [user, other_user]
                rooms.append(room)
        else:
            rooms = [
                room for room in
                Room.objects.filter(users=user).distinct()
            ]

        # Send the room list back to the user
        self.send({
            'type': constants.RECEIVE_ROOMS,
            'rooms': [
                {'id': room.id, 'name': room.name(user)}
                for room in rooms
            ],
        })

        # Broadcast the user's joining
        for room in rooms:
            # Pre-create a room channel
            room_channel = self.get_room_channel(room.id)
            self.add(room_channel)

            if user_created:
                other_user = room.name(user)  # FIXME when creating group chats

                # Attach the other users' open socket channels to the room
                other_channels = channel_layers[DEFAULT_CHANNEL_LAYER]._group_channels(
                    self.get_control_channel(other_user)
                )
                for channel in other_channels:
                    Group(room_channel).add(channel)

                # Notify the other users that a new user was created
                self.send_to_group(self.get_control_channel(other_user), {
                    'type': constants.RECEIVE_ROOMS,
                    'rooms': [
                        {'id': room.id, 'name': room.name(other_user)}
                        for room in rooms
                    ],
                })

    def SEND_MESSAGE(self, action):
        username = self.message.channel_session['user']

        # TODO Check that the user is a member of that room (prevent
        # cross posting into rooms she lacks membership too)
        room = Room.objects.get(id=action['roomId'])

        user = User.objects.get(username=username)
        m = Message.objects.create(
            user=user,
            room=room,
            content=action['content'],
        )

        # Broadcast the message to the room
        room_channel = self.get_room_channel(room.id)
        self.send_to_group(room_channel, {
            'type': 'RECEIVE_MESSAGES',
            'messages': [{
                'id': m.id,
                'roomId': room.id,
                'content': m.content,
                'timestamp': timestamp(m.timestamp),
                'user': username,
            }],
        })

    def REQUEST_MESSAGES(self, action):
        # latest_id, room

        params = Q()

        if 'roomId' in action:
            params &= Q(room_id=action['roomId'])
        if 'user' in action:
            params &= Q(room__users__username=action['user'])
        if 'lastMessageId' in action:
            # Any messages that occured at or later than time of lastMessage
            prior = Message.objects.get(id=action['lastMessageId'])
            params &= Q(timestamp__gte=prior.timestamp)
        if 'firstMessageId' in action:
            # Any messages that occured before the than time of lastMessage
            prior = Message.objects.get(id=action['firstMessageId'])
            params &= Q(timestamp__lte=prior.timestamp)

        messages = Message.objects.filter(
            params
        ).select_related(
            'user'
        ).order_by(
            # Get descending, because of LIMIT, but later reverse order
            # in Python to assist browser's sort
            '-timestamp', '-id'
        )[:50]

        # Reverse since messages displayed ascending
        messages = reversed(messages)

        # Return messages to the user
        self.send({
            'type': 'RECEIVE_MESSAGES',
            'messages': [{
                'id': m.id,
                'roomId': m.room_id,
                'content': m.content,
                'timestamp': timestamp(m.timestamp),
                'user': m.user.username,
            } for m in messages],
        })
