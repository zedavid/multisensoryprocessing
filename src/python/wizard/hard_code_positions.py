from furhat import connect_to_iristk

FURHAT_IP = '192.168.0.117'
FURHAT_AGENT_NAME = 'furhat6'

with connect_to_iristk(FURHAT_IP) as furhat_client:

    #furhat_client.say(FURHAT_AGENT_NAME, 'you\'re the werewolf') # Make furhat say hello
    furhat_client.gesture(FURHAT_AGENT_NAME,'sleep')
    #furhat_client.gaze(FURHAT_AGENT_NAME, {'x':0.45,'y':0,'z':2.67})

    input() # Press enter to quit