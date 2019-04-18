import ReconnectingWebSocket from 'shopify-reconnecting-websocket';
import ActionTypes from '../constants';
import _ from 'lodash';
import { loginUser, selectRoom } from '../actions';


const receiveSocketMessage = (store, action) => {
  /* We cheat by using the Redux-style Actions as our
   * communication protocol with the server. This hack allows
   * the server to directly act as a Action Creator, which we
   * simply `dispatch()`.  Consider separating communication format
   * from client-side action API.
   */
  switch (action.type) {
    // TODO Single Message Notification
    /*
       case ActionTypes.RECEIVE_MESSAGE:
       if ('Notification' in window) {
       Notification.requestPermission().then(function(permission) {
       if (permission === 'granted') {
       const n = new Notification(message.room, {
       body: message.content,
       });
       n.onclick(function(event){
       // event.preventDefault();
       // open the room that contains this message
       });
       setTimeout(n.close.bind(n), 3000);
       }
       });
       ... continue to dispatch() */
    case ActionTypes.RECEIVE_ROOMS:
      store.dispatch(action);

      // For the intial state, just open the first chat room.
      // TODO Should be the last-opened room (via Cookie, server, or max ID)
      const state = store.getState();
      const rooms = action.rooms;
      if (state.currentRoomId === null && rooms.length > 0) {
        selectRoom(rooms[0])(store.dispatch);
      }
      break;
    case ActionTypes.RECEIVE_MESSAGES:
    default:
      return store.dispatch(action);
  }
};

const reconnect = (state) => {
  // Re-login (need user on channel_session)
  loginUser(state.currentUser)();

  // TODO Delay the REQUEST_MESSAGES until after the LOGIN returns
  // Ensure we did not miss any messages
  const lastMessage = _.maxBy(state.messages, (m) => m.id);
  ChatAPI.send({
    type: ActionTypes.REQUEST_MESSAGES,
    lastMessageId: typeof lastMessage === 'undefined' ? 0 : lastMessage.id,
    user: state.currentUser,
  });
};


// TODO Consider re-implementing ChatAPI as a class, instead of using a
// module-level global
// FIXME on error / reconnect
let _socket = null;

export const ChatAPI = {
  connect: () => {
    // Use wss:// if running on https://
    const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${scheme}://${window.location.host}/chat`;
    _socket = new ReconnectingWebSocket(url);
  },

  listen: (store) => {
    _socket.onmessage = (event) => {
      const action = JSON.parse(event.data);
      receiveSocketMessage(store, action);
    };

    _socket.onopen = () => {
      const state = store.getState();

      // On Reconnect, need to re-login, so the channel_session['user']
      // is populated
      if (state.currentUser !== null) {
        reconnect(state);
      }
    };
  },

  send: (action) => {
    _socket.send(JSON.stringify(action));
  },
};

//const api = new ChatAPI();
//export default ChatAPI;
