import React from 'react';
import { shallow } from 'enzyme';
import { expect } from 'chai';

import Message from '../Message.react';


describe('<Message />', () => {
  it('renders content', () => {
    const ts = 1468461958836;
    const wrapper = shallow(
      <Message user="bob" content="hello world" timestamp={ts} />
    );
    expect(wrapper.hasClass('message')).to.equal(true);

    // Had issues using .contains(), so using find().text()
    expect(wrapper.find('.user').text()).to.equal('bob:');
    expect(wrapper.find('.timestamp').text()).to.equal(
      'September 16th, 11:40 AM'
    );
    expect(wrapper.find('.content').text()).to.equal('hello world');
  });
});
