"""
This file is based somewhat over a file made by someone named MegaLoler which you can find here:
http://pastebin.com/0CYCisB5 since this file is rather old, some changes has been made.
Also, big up to notnola who has made changes to rtmp_protocol.py thereby enabling broadcast to work.
I have tried to put in as many comments as i could for new developers.
"""

import time
import socket
import thread
import random
import webbrowser
from xml.dom.minidom import parseString
import requests
import rtmp_protocol


DEBUG = True


def create_random_string(min_length, max_length, upper=False):
    """
    Creates a random string of letters and numbers.
    :param min_length: int the minimum length of the string
    :param max_length: int the maximum length of the string
    :param upper: bool do we need upper letters
    :return: random str of letters and numbers
    """
    randlength = random.randint(min_length, max_length)
    junk = 'abcdefghijklmnopqrstuvwxyz0123456789'
    if upper:
        junk += 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    return ''.join((random.choice(junk) for i in xrange(randlength)))


def consol_write(msg):
    """
    Prints messages to the console.
    :param msg: the message str to write
    :return: None
    """
    ts = time.strftime('%H:%M:%S')
    info = '[' + ts + '] ' + msg
    print(info)


def random_color():
    """
    Get a random tinychat color.
    :return: str random color
    """
    colors = ['#000000', '#7db257', '#a78901', '#9d5bb5', '#5c1a7a', '#c53332', '#821615', '#a08f23',
              '#487d21', '#c356a3', '#1d82eb', '#919104', '#b9807f', '#7bb224', '#1965b6', '#32a5d9']
    return random.choice(colors)


class RoomUser:
    """
    A object to hold info about a user.
    Each user will have a object associated with there username.
    The object is used to store information about the user.
    """
    def __init__(self, nick, uid=None, last_msg=None):
        self.nick = nick
        self.id = uid
        self.last_msg = last_msg
        self.is_mod = False
        self.has_power = False
        self.user_account = None
        self.is_broadcasting = False


class TinychatRTMPClient:
    """ Manages a single room connection to a given room. """
    def __init__(self, room, tcurl=None, app=None, room_type=None, nick=None, account=None,
                 password=None, room_pass=None, ip=None, port=None, proxy_ip=None, proxy_port=None, module_type=0):
        self.roomname = room
        self.tc_url = tcurl
        self.app = app
        self.roomtype = room_type
        self.client_nick = nick
        self.account = account
        self.password = password
        self.room_pass = room_pass
        self.ip = ip
        self.port = port
        self.proxy_ip = proxy_ip
        self.proxy_port = proxy_port
        self.module_type = module_type
        self.request_session = requests.session()
        self.swf_url = u'http://tinychat.com/embed/Tinychat-11.1-1.0.0.0640.swf?version=1.0.0.0640/[[DYNAMIC]]/8'
        self.embed_url = u'http://tinychat.com/' + self.roomname
        self.autoop = u'none'
        self.prokey = ''
        self.client_id = None
        self.is_connected = False
        self.is_client_mod = False
        self.room_users = {}
        self.is_reconnected = False

    def prepare_connect(self):
        """ Gather necessary connection parameters before attempting to connect. """
        if self.account and self.password:
            if len(self.account) > 3:
                login = self.post_login(self.account, self.password)
                if 'pass' in login['cookies']:
                    consol_write('Logged in as: ' + login['cookies']['user'])
                    consol_write('Trying to parse hashes..')
                    profile_html = self.web_request(self.embed_url)
                    if ', autoop: "' in profile_html['content']:
                        self.autoop = profile_html['content'].split(', autoop: "')[1].split('"')[0]
                        consol_write('Found autoop hash: ' + self.autoop)
                    if ', prokey: "' in profile_html['content']:
                        self.prokey = profile_html['content'].split(', prohash: "')[1].split('"')[0]
                        consol_write('Found prohash: ' + self.prokey)
                else:
                    consol_write('Log in Failed')
                    self.account = raw_input('Enter account: (optional)')
                    if self.account:
                        self.password = raw_input('Enter password: ')
                    self.prepare_connect()
            else:
                consol_write('Account name is to short.')
                self.account = raw_input('Enter account: ')
                self.password = raw_input('Enter password: ')
                self.prepare_connect()

        consol_write('Parsing room config xml...')
        config = self.get_roomconfig_xml(self.roomname, self.room_pass)

        while config == 'PW':
            self.room_pass = raw_input('The room is password protected. Enter the password: ')
            if not self.room_pass:
                self.roomname = raw_input('Enter room name: ')
                self.room_pass = raw_input('Enter room pass: (optional)')
                self.account = raw_input('Enter account: (optional)')
                self.password = raw_input('Enter password: (optional)')
                self.prepare_connect()
            else:
                config = self.get_roomconfig_xml(self.roomname, self.room_pass)
                if config != 'PW':
                    break
                else:
                    consol_write('Password Failed.')

        self.ip = config['ip']
        self.port = config['port']
        self.tc_url = config['tcurl']
        self.app = config['app']
        self.roomtype = config['roomtype']

        consol_write('Config info...\n' +
                     'Server Url: ' + self.tc_url + '\n' +
                     'Application: ' + self.app + '\n' +
                     'Room Type: ' + self.roomtype + '\n\n' +
                     '============ CONNECTING ============\n')

        self.connect()

    def connect(self):
        """ Attempts to make a RTMP connection with the given connection parameters. """
        if not self.is_connected:
            try:
                self.recaptcha()
                cauth_cookie = self.get_cauth_cookie()
                if self.module_type == 0:
                    self.connection = rtmp_protocol.RtmpClient(self.ip, self.port, self.tc_url, self.embed_url, self.swf_url, self.app)
                    self.connection.connect([self.roomname, self.autoop, self.roomtype, u'tinychat', self.account, self.prokey, cauth_cookie])
                self.is_connected = True
                self.callback()
            except Exception as e:
                if DEBUG:
                    print(e.message)
                    self.is_connected = False

    def disconnect(self):
        """ Closes the RTMP connection with the remote server. """
        if self.is_connected:
            try:
                self.is_connected = False
                self.connection.socket.shutdown(socket.SHUT_RDWR)
            except Exception as e:
                if DEBUG:
                    print(e.message)

    def reconnect(self):
        """ Reconnect to a room with the connection parameters already set. """
        self.is_reconnected = True
        self.room_users = {}
        consol_write('============ RECONNECTING IN 5 SECONDS ============')
        self.disconnect()
        time.sleep(5)
        self.connect()

    def callback(self):
        """ Callback loop that reads from the RTMP stream. """
        while self.is_connected:
            try:
                iparam0 = 0
                amf0_data = self.connection.reader.next()
                amf0_cmd = amf0_data['command']
                cmd = amf0_cmd[0]

                if cmd == '_result':
                    print(amf0_data)

                elif cmd == '_error':
                    print(amf0_data)

                elif cmd == 'onBWDone':
                    self.on_bwdone()

                elif cmd == 'onStatus':
                    self.on_onstatus()

                elif cmd == 'registered':
                    self.client_id = amf0_cmd[4]
                    self.on_registered()

                elif cmd == 'join':
                    usr_join_id = amf0_cmd[3]
                    user_join_nick = amf0_cmd[4]
                    self.on_join(usr_join_id, user_join_nick)

                elif cmd == 'joins':
                    id_nick = amf0_cmd[4:]
                    if len(id_nick) is not 0:
                        while iparam0 < len(id_nick):
                            user_id = id_nick[iparam0]
                            user_nick = id_nick[iparam0 + 1]
                            self.on_joins(user_id, user_nick)
                            iparam0 += 2

                elif cmd == 'joinsdone':
                    self.on_joinsdone()

                elif cmd == 'oper':
                    oper_id_name = amf0_cmd[3:]
                    while iparam0 < len(oper_id_name):
                        oper_id = str(oper_id_name[iparam0]).split('.0')
                        oper_name = oper_id_name[iparam0 + 1]
                        if len(oper_id) == 1:
                            self.on_oper(oper_id[0], oper_name)
                        iparam0 += 2

                elif cmd == 'deop':
                    deop_id = amf0_cmd[3]
                    deop_nick = amf0_cmd[4]
                    self.on_deop(deop_id, deop_nick)

                elif cmd == 'owner':
                    self.on_owner()

                elif cmd == 'avons':
                    avons_id_name = amf0_cmd[4:]
                    if len(avons_id_name) is not 0:
                        while iparam0 < len(avons_id_name):
                            avons_id = avons_id_name[iparam0]
                            avons_name = avons_id_name[iparam0 + 1]
                            self.on_avon(avons_id, avons_name)
                            iparam0 += 2

                elif cmd == 'pros':
                    pro_ids = amf0_cmd[4:]
                    if len(pro_ids) is not 0:
                        for pro_id in pro_ids:
                            pro_id = str(pro_id).replace('.0', '')
                            self.on_pro(pro_id)

                elif cmd == 'nick':
                    old_nick = amf0_cmd[3]
                    new_nick = amf0_cmd[4]
                    nick_id = amf0_cmd[5]
                    self.on_nick(old_nick, new_nick, nick_id)

                elif cmd == 'nickinuse':
                    self.on_nickinuse()

                elif cmd == 'quit':
                    quit_name = amf0_cmd[3]
                    quit_id = amf0_cmd[4]
                    self.on_quit(quit_id, quit_name)

                elif cmd == 'kick':
                    kick_id = amf0_cmd[3]
                    kick_name = amf0_cmd[4]
                    self.on_kick(kick_id, kick_name)

                elif cmd == 'banned':
                    self.on_banned()

                elif cmd == 'banlist':
                    banlist_id_nick = amf0_cmd[3:]
                    if len(banlist_id_nick) is not 0:
                        while iparam0 < len(banlist_id_nick):
                            banned_id = banlist_id_nick[iparam0]
                            banned_nick = banlist_id_nick[iparam0 + 1]
                            self.on_banlist(banned_id, banned_nick)
                            iparam0 += 2

                elif cmd == 'startbanlist':
                    pass

                elif cmd == 'topic':
                    topic = amf0_cmd[3]
                    self.on_topic(topic)

                elif cmd == 'from_owner':
                    owner_msg = amf0_cmd[3]
                    self.on_from_owner(owner_msg)

                elif cmd == 'privmsg':
                    msg_text = self._decode_msg(amf0_cmd[4])
                    # msg_color = amf0_cmd[5]
                    msg_sender = amf0_cmd[6]
                    self.on_privmsg(msg_text, msg_sender)

                elif cmd == 'notice':
                    notice_msg = amf0_cmd[3]
                    notice_msg_id = amf0_cmd[4]
                    if notice_msg == 'avon':
                        avon_name = amf0_cmd[5]
                        self.on_avon(notice_msg_id, avon_name)
                    elif notice_msg == 'pro':
                        self.on_pro(notice_msg_id)

                else:
                    consol_write('Unknown command:' + cmd)

            except Exception as e:
                if DEBUG:
                    print(e.message)

    # Callback events
    def on_result(self, result_info):
        pass

    def on_error(self, error_info):
        pass

    def on_bwdone(self):
        if not self.is_reconnected:
            thread.start_new_thread(self.start_auto_job_timer, (300000,))

    def on_onstatus(self):
        pass

    def on_registered(self):
        consol_write('registered with ID: ' + self.client_id + '. Trying to parse captcha key.')
        key = self.get_captcha_key()
        if key is None:
            consol_write('There was a problem parsing the captcha key. Key=' + key)
        else:
            consol_write('Captcha key found: ' + key)
            self.send_cauth_msg(key)
            self.set_nick()

    def on_join(self, uid, nick):
        user = self.find_user(nick)
        user.id = uid
        if uid != self.client_id:
            consol_write(nick + ':' + uid + ' joined the room.')

    def on_joins(self, uid, nick):
        user = self.find_user(nick)
        user.id = uid
        if uid != self.client_id:
            consol_write(nick + ':' + uid)

    def on_joinsdone(self):
        self.send_userinfo_request_to_all()

    def on_oper(self, uid, nick):
        user = self.find_user(nick)
        user.is_mod = True
        consol_write(nick + ':' + uid + ' is moderator.')

    def on_deop(self, uid, nick):
        consol_write(nick + ':' + uid + ' was deoped.')

    def on_owner(self):
        self.is_client_mod = True
        self.send_banlist_msg()

    def on_avon(self, uid, name):
        user = self.find_user(name)
        user.is_broadcasting = True
        consol_write(name + ':' + uid + ' is broadcasting.')

    def on_pro(self, uid):
        consol_write(uid + ' is pro.')

    def on_nick(self, old, new, uid):
        old_info = self.user_info(old)
        if old in self.room_users.keys():
            del self.room_users[old]
            self.room_users[new] = old_info
        if str(old).startswith('guest-') and uid != self.client_id:
            # Delete next line to remove user greetings.
            self.send_bot_msg('*Welcome to* ' + self.roomname + ' *' + new + '*', self.is_client_mod)
            self.send_userinfo_request_msg(new)
        consol_write(old + ':' + uid + ' changed nick to: ' + new)

    def on_nickinuse(self):
        self.nick_inuse()

    def on_quit(self, uid, name):
        del self.room_users[name]
        consol_write(name + ':' + uid + ' left the room.')

    def on_kick(self, uid, name):
        consol_write(name + ':' + uid + ' was banned.')

    def on_banned(self):
        consol_write('You are banned from this room.')

    def on_banlist(self, uid, nick):
        consol_write('Banned user: ' + nick + ':' + uid)

    def on_topic(self, topic):
        topic_msg = topic.encode('utf-8', 'replace')
        consol_write('room topic: ' + topic_msg)

    def on_from_owner(self, owner_msg):
        msg = str(owner_msg).replace('notice', '').replace('%20', ' ')
        consol_write(msg)

    def on_privmsg(self, msg, msg_sender):
        """
        Message controller.

        This method will figure out if the message is a userinfo request, userinfo response, media
        playing/stoping or if it's a private message. If it's not, we pass the message along to message_handler.

        :param msg: str message.
        :param msg_sender: str the sender of the message.
        """
        if msg.startswith('/'):
            msg_cmd = msg.split(' ')
            if msg_cmd[0] == '/userinfo':
                if msg_cmd[1] == '$request':
                    self.info_request_from(msg_sender)
                elif msg_cmd[1] == '$noinfo':
                    self.user_is_guest(msg_sender)
                else:
                    self.user_has_account(msg_sender, msg_cmd[1])

            elif msg_cmd[0] == '/msg':
                private_msg = ' '.join(msg_cmd[2:])
                self.private_msg_from(msg_sender, private_msg)

            elif msg_cmd[0] == '/mbs':
                self.user_is_playing_media(msg_cmd[1], msg_sender, msg_cmd[2])

            elif msg_cmd[0] == '/mbc':
                self.user_closed_media(msg_cmd[1], msg_sender)

            elif msg_cmd[0] == 'mbpa':
                pass

            elif msg_cmd[0] == '/mbpl':
                pass

            elif msg_cmd[0] == '/mbsk':
                pass
        else:
            self.message_handler(msg_sender, msg.encode('ascii', 'ignore'))

    # Message Handler
    def message_handler(self, msg_sender, msg):
        """
        Message handler.
        :param msg_sender: str the user sending a message
        :param msg: str the message
        """
        consol_write(msg_sender + ':' + msg)

    # Private Message From
    def private_msg_from(self, usr_nick, prv_msg):
        """
        A user private message us.
        :param usr_nick: str the suer sending the private message.
        :param prv_msg: str the private message.
        """
        consol_write('Private message from ' + usr_nick + ':' + prv_msg)

    # Media Events
    def user_is_playing_media(self, media_type, usr_nick, video_id):
        """
        A user started a media broadcast.
        :param media_type: str the type of media. youTube or soundCloud.
        :param usr_nick: str the user name of the user playing media.
        :param video_id: str the youtube ID or souncloud trackID.
        """
        consol_write(usr_nick + ' is playing ' + media_type + ' ' + video_id)

    def user_closed_media(self, media_type, usr_nick):
        """
        A user closed a media broadcast.
        :param media_type: str the type of media. youTube or soundCloud.
        :param usr_nick: str the user name of the user closing the media.
        """
        consol_write(usr_nick + ' closed the ' + media_type)

    # User Info Events
    def info_request_from(self, usr_nick):
        """
        A user requests our user info.
        :param usr_nick: str the user name of the user requesting our user info.
        """
        self.send_userinfo_response_to(usr_nick, self.roomname)
        consol_write(usr_nick + ' requests userinfo.')

    def user_is_guest(self, usr_nick):
        """
        The user tells us that they are a guest.
        :param usr_nick: str the user that is a guest.
        """
        user = self.find_user(usr_nick)
        user.user_account = False
        consol_write(usr_nick + ' is not signed in.')

    def user_has_account(self, usr_nick, usr_acc):
        """
        A user replies to our user info request, that they have a account name.

        :param usr_nick: str the user name of the user having an account.
        :param usr_acc: str the account that the user has.
        """
        user = self.find_user(usr_nick)
        user.user_account = usr_acc
        consol_write(usr_nick + ' has account: ' + usr_acc)

    # Find User
    def find_user(self, usr_nick):
        """
        Find the user object for a given user name.
        The problem with this method is that if you have a command to ban with, and you are using this method to look up
        the id of the user, and the user name you are trying to ban is NOT in the room_users dict,
        it will ad a user name in the room_users dict with a user info object where all the attributes
        except nick will be set to there defaults.

        :param usr_nick: str the user name of the user we want to find info for.
        :return: object a user object containing user info.
        """
        if usr_nick not in self.room_users.keys():
            self.room_users[usr_nick] = RoomUser(usr_nick)
        return self.room_users[usr_nick]

    def user_info(self, usr_nick):
        """
        Find the user object for a given user name.
        Instead of adding to the user info object, we return None if the user name is NOT in the room_users dict.
        We use this method when we are getting user input to look up.

        :param usr_nick: str the user name to find info for.
        :return: object or None if no user name is in the room_users dict.
        """
        if usr_nick in self.room_users.keys():
            return self.room_users[usr_nick]
        return None

    # Message Functions
    def send_bauth_msg(self):
        """
        Get and send the bauth key needed before we can start a broadcast.
        """
        bauth_key = self.get_bauth_token()
        self._sendCommand('bauth', [u'' + bauth_key])

    def send_cauth_msg(self, cauthkey):
        """
        Send the cauth key message with a working cauth key, we need to send this before we can chat.
        :param cauthkey: str a working cauth key.
        """
        self._sendCommand('cauth', [u'' + cauthkey])

    def send_owner_run_msg(self, msg):
        """
        Send owner run message. The client has to be mod when sending this message.
        :param msg: the message str to send.
        """
        self._sendCommand('owner_run', [u'notice' + msg.replace(' ', '%20')])

    def send_bot_msg(self, msg, is_mod=False):
        """
        Send a message in the color black.
        :param msg: str the message to send.
        :param is_mod: bool if True we send owner run message instead, else we send a normal message but in the color black.
        :return:
        """
        if is_mod:
            self.send_owner_run_msg(msg)
        else:
            self._sendCommand('privmsg', [u'' + self._encode_msg(msg), u'#000000,en'])

    def send_private_bot_msg(self, msg, nick):
        """
        Send a private message to a user in the color black.
        :param msg: str the message to send.
        :param nick: str the user to receive the message.
        """
        self._sendCommand('privmsg', [u'' + self._encode_msg('/msg ' + nick + ' ' + msg), u'#000000,en'])

    def send_chat_msg(self, msg):
        """
        Send a chat room message with a random color.
        :param msg: str the message to send.
        """
        self._sendCommand('privmsg', [u'' + self._encode_msg(msg), u'' + random_color() + ',en'])

    def send_private_msg(self, msg, nick):
        """
        Send a private message to a user with a random color.
        :param msg: str the private message to send.
        :param nick: str the user name to receive the message.
        """
        self._sendCommand('privmsg', [u'' + self._encode_msg('/msg ' + nick + ' ' + msg), u'' + random_color() + ',en', u'n' + self.find_user(nick).id + '-' + nick])

    def send_userinfo_response_to(self, nick, info):
        """
        Send a userinfo response to a user that requests our userinfo.
        :param nick: str the user name to send the userinfo to.
        :param info: str the user info to send. This should be a account name.
        """
        self._sendCommand('privmsg', [u'' + self._encode_msg('/userinfo' + ' ' + u'' + info), '#0,en', u'n' + self.find_user(nick).id + '-' + nick])

    def send_userinfo_request_msg(self, nick):
        """
        Request userinfo from a user.
        :param nick: str the user name of the user we want info from.
        """
        user = self.find_user(nick)
        if user.is_broadcasting:
            self._sendCommand('privmsg', [u'' + self._encode_msg('/userinfo $request'), '#0,en', u'b' + user.id + '-' + nick])
        else:
            self._sendCommand('privmsg', [u'' + self._encode_msg('/userinfo $request'), '#0,en', u'n' + user.id + '-' + nick])

    def send_userinfo_request_to_all(self):
        """
        Request userinfo from all users.
        Only used when we join a room.
        """
        self._sendCommand('privmsg', [u'' + self._encode_msg('/userinfo $request'), '#0,en'])

    def send_undercover_msg(self, nick, msg):
        """
        Send a 'undercover' message.
        This is a special message that appears in the main chat, but is only visible to the user it is sent to.
        It can also be used to play 'private' youtubes with.

        :param nick: str the user name to send the message to.
        :param msg: str the message to send.
        """
        user = self.find_user(nick)
        if user.is_broadcasting:
            self._sendCommand('privmsg', [u'' + self._encode_msg(msg), '#0,en', u'b' + user.id + '-' + nick])
        else:
            self._sendCommand('privmsg', [u'' + self._encode_msg(msg), '#0,en', u'n' + user.id + '-' + nick])

    def set_nick(self):
        """
        Send the nick message.
        """
        if not self.client_nick:
            self.client_nick = create_random_string(5, 25)
        consol_write('Setting nick: ' + self.client_nick)
        self._sendCommand('nick', [u'' + self.client_nick])

    def send_ban_msg(self, nick, uid):
        """
        Send ban message. The client has to be mod when sending this message.
        :param nick: str the user name of the user we want to ban.
        :param uid: str the ID of the user we want to ban.
        """
        self._sendCommand('kick', [u'' + nick, uid])

    def send_forgive_msg(self, uid):
        """
        Send forgive message. The client has to be mod when sending this message.
        :param uid: str the ID of the user we want to forgive.
        """
        self._sendCommand('forgive', [u'' + uid])
        self.send_banlist_msg()

    def send_banlist_msg(self):
        """
        Send banlist message. The client has to be mod when sending this message.
        :return:
        """
        self._sendCommand('banlist', [])

    def send_topic_msg(self, topic):
        """
        Send a room topic message. The client has to be mod when sending this message.
        :param topic: str the room topic.
        """
        self._sendCommand('topic', [u'' + topic])

    def send_close_user_msg(self, nick):
        """
        Send close user broadcast message. The client has to be mod when sending this message.
        :param nick: str the user name of the user we want to close.
        """
        self._sendCommand('owner_run', [ u'_close' + nick])

    def play_youtube(self, video_id):
        """
        Start a youtube video.
        :param video_id: str the youtube video ID.
        """
        self.send_chat_msg('/mbs youTube ' + str(video_id) + ' 0')

    def stop_youtube(self):
        """
        Stop/Close a youtube video.
        """
        self.send_chat_msg('/mbc youTube')

    def play_soundcloud(self, track_id):
        """
        Start a soundcloud video.
        :param track_id: str soundcloud track ID.
        """
        self.send_chat_msg('/mbs soundCloud ' + str(track_id) + ' 0')

    def stop_soundcloud(self):
        """
        Stop/Close a soundcloud video.
        """
        self.send_chat_msg('/mbc soundCloud')

    def nick_inuse(self):
        """
        Choose a different user name if the one we chose originally was being used.
        """
        self.client_nick += str(random.randint(0, 10))
        consol_write('Nick already taken. Changing nick to: ' + self.client_nick)
        self.set_nick()

    # Message Cunstruction.
    def _sendCommand(self, cmd, params=[]):
        """
        Calls remote procedure calls (RPC) at the receiving end.
        :param cmd: str remote command.
        :param params: list command parameters.
        """
        msg = {'msg': rtmp_protocol.DataTypes.COMMAND, 'command': [u'' + cmd, 0, None] + params}
        self.connection.writer.write(msg)
        self.connection.writer.flush()

    def _sendCreateStream(self):
        """
        Send createStream message.
        """
        msg = {'msg': rtmp_protocol.DataTypes.COMMAND, 'command': [u'' + 'createStream', 12, None]}
        consol_write('Sending createStream message.')
        self.connection.writer.write(msg)
        self.connection.writer.flush()

    def _sendCloseStream(self):
        """
        Send closeStream message.
        """
        msg = {'msg': rtmp_protocol.DataTypes.COMMAND, 'command': [u'' + 'closeStream', 0, None]}
        consol_write('Closing stream.')
        self.connection.writer.writepublish(msg)
        self.connection.writer.flush()

    def _sendPublish(self):
        """
        Send publish message.
        """
        msg = {'msg': rtmp_protocol.DataTypes.COMMAND, 'command': [u'' + 'publish', 0, None, u'' + self.client_id, u'' + 'live']}
        consol_write('Sending publish message.')
        self.connection.writer.writepublish(msg)
        self.connection.writer.flush()

    def _decode_msg(self, msg):
        """
        Decode str from comma separated decimal to normal text str.
        :param msg: str the encoded message.
        :return: str normal text.
        """
        chars = msg.split(',')
        msg = ''
        for i in chars:
            msg += chr(int(i))
        return msg

    def _encode_msg(self, msg):
        """
        Encode normal text str to comma separated decimal.
        :param msg: str the normal text to encode
        :return: comma separated decimal str.
        """
        return ','.join(str(ord(char)) for char in msg)

    # Timed auto functions.
    def auto_job_do_roomconfig_request(self):
        """
        Like using tinychat with a browser, we call this method every ~5 minutes.
        See line 228 at http://tinychat.com/embed/chat.js
        """
        if self.is_connected:
            self.get_roomconfig_xml(self.roomname, self.room_pass)

    def start_auto_job_timer(self, interval):
        """
        The auto timer for auto_job_do_roomconfig_request.
        :param interval: int milliseconds.
        """
        ts_now = int(time.time() * 1000)
        while True:
            counter = int(time.time() * 1000)
            if counter == ts_now + interval:
                self.auto_job_do_roomconfig_request()
                self.start_auto_job_timer(interval)
                break

    # Requests Functions.
    def web_request(self, url, json=False):
        """
        All method's making GET requests will use this method.
        :param url: str the url to the web content.
        :param json: bool set to True if the expected response is json.
        :return: dict['content', 'cookies', 'headers'] or None on json decode error.
        """
        header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:39.0) Gecko/20100101 Firefox/39.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Referer': 'http://tinychat.com/embed/Tinychat-11.1-1.0.0.0640.swf?version=1.0.0.0640'
        }
        gr = self.request_session.request(method='GET', url=url, headers=header)

        if json is True:
            try:
                content = gr.json()
            except ValueError:
                content = None
        else:
            content = gr.text

        return {'content': content, 'cookies': gr.cookies, 'headers': gr.headers}

    def post_login(self, account, password):
        """
        This method's only job is, to make a POST to the tinychat login page,
        and add the received cookies to our request session. The returned response is not used anywhere, but i thought
        it could be useful for debug situations.

        :param account: str login account name.
        :param password: str login password.
        :return: dict['content', 'cookies', 'headers']
        """
        header = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:39.0) Gecko/20100101 Firefox/39.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Referer': 'http://tinychat.com/login'
        }

        data = {
            'form_sent': '1',
            'referer': '',
            'next': '',
            'username': account,
            'password':  password,
            'passwordfake': 'Password',
            'remember': '1'
        }

        post_url = 'http://tinychat.com/login'
        pr = self.request_session.request(method='POST', url=post_url, data=data, headers=header, allow_redirects=False)

        return {'content': pr.text, 'cookies': pr.cookies, 'headers': pr.headers}

    # Tinychat API functions.
    def get_roomconfig_xml(self, room, roompass=None):
        """
        Gets the RTMP parameters from tinychat API.
        :param room: str the room name.
        :param roompass: str the room pass(if needed)
        :return: dict['tc_url', 'ip', 'port', 'app', 'roomtype'] or str PW if room is password protected.
        """
        if roompass:
            xmlurl = 'http://apl.tinychat.com/api/find.room/%s?site=tinychat&password=%s&url=tinychat.com' % \
                     (room, roompass)
        else:
            xmlurl = 'http://apl.tinychat.com/api/find.room/%s?site=tinychat&url=tinychat.com' % room

        web_content = self.web_request(xmlurl)
        xml = parseString(web_content['content'])

        root = xml.getElementsByTagName('response')[0]
        result = root.getAttribute('result')
        if result == 'PW':
            return result
        else:
            roomtype = root.getAttribute('roomtype')
            tc_url = root.getAttribute('rtmp')
            rtmp_parts = tc_url.split('/')
            app = rtmp_parts[3]
            ip_port_parts = rtmp_parts[2].split(':')
            ip = ip_port_parts[0]
            port = int(ip_port_parts[1])

            return {'tcurl': tc_url, 'ip': ip, 'port': port, 'app': app, 'roomtype': roomtype}

    def tinychat_user_info(self, tc_account):
        """
        Find info for a given tinychat account using tinychat API.
        :param tc_account: str tinychat account to find info for.
        :return: dict['username', 'tinychat_id', 'last_activ'] or None on error.
        """
        xmlurl = 'http://tinychat.com/api/tcinfo?format=xml&username=%s' % tc_account
        web_content = self.web_request(xmlurl)
        try:
            xml = parseString(web_content['content'])
            root = xml.getElementsByTagName('result')[0]
            username = root.getAttribute('username')
            user_id = root.getAttribute('id')
            last_active = time.ctime(int(root.getAttribute('last_active')))

            return {'username': username, 'tinychat_id': user_id, 'last_activ': last_active}
        except Exception as e:
            if DEBUG:
                consol_write(e.message)
            return None

    def spy_info(self, room):
        """
        Find room information for a given room name using tinychat API.
        The information will be, how many mods(mod_count), how many that are broadcasting(broadcaster_count)
        how many users(total_count) and all the user names(users).
        :param room: str the room name we want info for.
        :return: dict['mod_count', 'broadcaster_count', 'total_count', 'users'] or PW on password protected rooms or None on error.
        """
        xmlurl = 'http://api.tinychat.com/%s.xml' % room
        passcheck = self.get_roomconfig_xml(room)
        if passcheck == 'PW':
            return passcheck
        else:
            web_content = self.web_request(xmlurl)
            xml = parseString(web_content['content'])
            try:
                root = xml.getElementsByTagName('tinychat')[0]
                mod_count = root.getAttribute('mod_count')
                broadcaster_count = root.getAttribute('broadcaster_count')
                total_count = root.getAttribute('total_count')
                if total_count > 0:
                    u = []
                    names = xml.getElementsByTagName('names')
                    for name in names:
                        u.append(name.firstChild.nodeValue)
                    users = ', '.join(u)
                    return {'mod_count': mod_count, 'broadcaster_count': broadcaster_count, 'total_count': total_count, 'users': users}
            except IndexError:
                return None

    def get_bauth_token(self):
        """
        Get the bauth token needed before we can broadcast.
        :return: str token hash or str PW when password protected broadcast is enabled.
        """
        xmlurl = 'http://tinychat.com/api/broadcast.pw?site=tinychat&name=%s&nick=%s&id=%s' % \
                 (self.roomname, self.client_nick, self.client_id)

        web_content = self.web_request(xmlurl)
        xml = parseString(web_content['content'])

        root = xml.getElementsByTagName('response')[0]
        result = root.getAttribute('result')
        if result == 'PW':
            return result
        else:
            token = root.getAttribute('token')
            return token

    def get_captcha_key(self):
        """
        Get the captcha key needed before we can start chatting.
        :return: str captcha key or None
        """
        url = 'http://tinychat.com/api/captcha/check.php?room=tinychat^%s&guest_id=%s' % (self.roomname, self.client_id)
        json_data = self.web_request(url, json=True)

        if 'key' in json_data['content']:
            return json_data['content']['key']
        else:
            return None

    def get_cauth_cookie(self):
        """
        Get the cauth 'cookie' that is part of the RTMP connect message.
        :return: str cauth cookie
        """
        ts = int(round(time.time() * 1000))
        url = 'http://tinychat.com/cauth?room=%s&t=%s' % (self.roomname, str(ts))
        json_data = self.web_request(url, json=True)

        if 'cookie' in json_data['content']:
            return json_data['content']['cookie']
        else:
            return None

    def recaptcha(self):
        """
        Check recaptcha. We will use our default browser to open the recaptcha challenge to solve.
        The return cookies is not used in the code, as request session will take care of it for us.

        :return: cookies dict (only used for debugging purposes)
        """
        t = str(random.uniform(0.9, 0.10))
        url = 'http://tinychat.com/cauth/captcha?%s' % t
        response = self.web_request(url, json=True)
        if response['content']['need_to_solve_captcha'] == 1:
            link = 'http://tinychat.com/cauth/recaptcha?token=%s' % response['content']['token']
            webbrowser.open(link, new=1)
            raw_input('Click enter to continue.')
        return response['cookies']

if __name__ == '__main__':
    room_name = raw_input('Enter room name: ')
    nickname = raw_input('Enter nick name: (optional) ')
    room_password = raw_input('Enter room password: (optional) ')
    login_account = raw_input('Login account: (optional)')
    login_password = raw_input('Login password: (optional)')

    client = TinychatRTMPClient(room_name, nick=nickname, account=login_account,
                                password=login_password, room_pass=room_password)

    thread.start_new_thread(client.prepare_connect, ())
    while not client.is_connected: time.sleep(1)
    while client.is_connected:
        chat_msg = raw_input()
        if chat_msg.lower() == 'q':
            client.disconnect()
        else:
            if client.is_client_mod:
                client.send_owner_run_msg(chat_msg)
            else:
                client.send_chat_msg(chat_msg)
