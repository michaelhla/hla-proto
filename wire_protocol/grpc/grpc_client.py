# Python program to implement client side of chat room.
import threading
import select
import sys
import grpc

import wire_pb2 as chat
import wire_pb2_grpc as rpc

MAX_MESSAGE_LENGTH = 280
MAX_RECIPIENT_LENGTH = 50

if len(sys.argv) != 3:
    print("Correct usage: script, IP address, port number")
    exit()
IP_address = str(sys.argv[1])
Port = sys.argv[2]
channel = grpc.insecure_channel(IP_address + ':' + Port)
conn = rpc.BidirectionalStub(channel)

# global variable to track account state
# since only one thread that writes to this
# and listen thread is only started after a change to username (and only checks once), thread safe
username = ''

# thread for listening to server
# each client has a "sending" thread and a "listening" thread
listen_thread = None

# called when logged in, exits when logged out on server side


def listen():
    if username != '':
        this_acc = chat.Account(type=0, username=username,
                                connection=str(channel))  # pass through current account info
        try:
            # call client stream and update terminal as stream comes in
            for text in conn.ClientStream(this_acc):
                print("<"+text.sender+">: " + text.message)
        except Exception as e:
            print(e)

# processes terminal input, and makes a rpc to the server based on input


def process(message):
    global username
    global listen_thread
    message = message.rstrip()
    # Messages are first entered as types, and are tagged based on those types
    # CREATE ACCOUNT
    if message.find('Create Account') == 0:
        if username == '':  # check login state
            pmessage = input('username:').rstrip()
            if len(pmessage) > MAX_RECIPIENT_LENGTH:
                print('username must be under 50 characters')
                res = None
                return res
            acct = chat.Account(type=3, username=pmessage,
                                connection=str(channel))
            res = conn.ChangeAccountState(acct)
            # if creation was successful, open listening thread
            if res.status == 0:
                username = pmessage
                listen_thread = threading.Thread(
                    target=listen, daemon=True)
                listen_thread.start()
        else:
            print(f'Currently signed in as {username}, please log out first')
            res = None
    # LOGIN
    elif message.find('Login') == 0:
        if username == '':
            pmessage = input("username:").rstrip()
            acct = chat.Account(type=0, username=pmessage,
                                connection=str(channel))
            # create account with account buffer
            res = conn.ChangeAccountState(acct)
            # if creation was successful, open listening thread
            if res.status == 0:
                username = pmessage
                listen_thread = threading.Thread(
                    target=listen, daemon=True)
                listen_thread.start()
        else:
            print(f'Currently signed in as {username}, please log out first')
            res = None
    # LOGOUT
    elif message.find('Logout') == 0:
        if username != '':
            acct = chat.Account(type=1, username=username,
                                connection=str(channel))
            res = conn.ChangeAccountState(acct)
            if res.status == 0:
                username = ''  # change global variable to null when logged out
        else:
            res = None
            print('Please log in first')
    # DELETE ACCOUNT
    elif message.find('Delete Account') == 0:
        if username != '':
            acct = chat.Account(type=2, username=username,
                                connection=str(channel))
            res = conn.ChangeAccountState(acct)
            username = ''
        else:
            res = None
            print('Please log in first')
    # SEND MESSAGE
    elif message.find("Send") == 0:
        if username != '':
            receiver = input('to: ').rstrip()  # clean recipient username
            text = input('begin message: ')
            if len(text) > MAX_MESSAGE_LENGTH:
                res = None
                print("Message must be under 250 characters")
                return res
            res = conn.ServerSend(chat.Text(sender=username,
                                            receiver=receiver, message=text))
        else:
            res = None
            print('Please log in first')
    # LIST ACCOUNTS
    elif message.find("List Accounts") == 0:
        query = input('search users: ').rstrip()  # queries follow regex
        number = int(input('number of matches: '))  # max number of matches
        results = conn.ListAccounts(chat.Query(match=query, number=number))
        print(results.list)
        res = chat.Res(status=0)
        if len(results.list) == 0:
            res.status = 1

    else:
        print('Input not recognized. Please try again.')
        return
    return res  # returns a res object with status to parse errors


print("Welcome to Messenger! Login or create an account to get started!")
# continuously accept input into terminal
while True:
    message = input()
    try:
        res = process(message)
        if res is not None:  # if some res returned, parse errors
            if res.status == 0:
                print('success')
            elif res.status == 1:
                print('Account(s) not found')
            elif res.status == 2:
                print('Username taken, enter prompt to try again')
            else:
                print('Unknown server error')
    except Exception as e:
        print(e)