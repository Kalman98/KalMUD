"""
A simple Multi-User Dungeon (MUD) game. Players can talk to each other, examine
their surroundings and move between rooms.

Some ideas for things to try adding:
    * More rooms to explore
    * An 'emote' command e.g. 'emote laughs out loud' -> 'Mark laughs out loud'
    * A 'whisper' command for talking to individual players
    * A 'shout' command for yelling to players in all rooms
    * Items to look at in rooms e.g. 'look fireplace' -> 'You see a roaring, glowing fire'
    * Items to pick up e.g. 'take rock' -> 'You pick up the rock'
    * Monsters to fight
    * Loot to collect
    * Saving players accounts between sessions
    * A password login
    * A shop from which to buy items

author: Mark Frimston - mfrimston@gmail.com
"""

import time
import json

# import the MUD server class
from mudserver import MudServer

# structure defining the rooms in the game. Try adding more rooms to the game!
with open('world.json') as json_data:
    rooms = json.load(json_data)
# structure where players are saved
with open('players.json') as json_data:
    players = json.load(json_data)

active_players = {}

# start the server
mud = MudServer()

# main game loop. We loop forever (i.e. until the program is terminated)
while True:

    # pause for 1/5 of a second on each loop, so that we don't constantly
    # use 100% CPU time
    time.sleep(0.2)

    # 'update' must be called in the loop to keep the game running and give
    # us up-to-date information
    mud.update()

    # go through any newly connected players
    for id in mud.get_new_players():

        # add the new player to the dictionary, noting that they've not been
        # named yet.
        # The dictionary key is the player's id number. Start them off in the
        # 'Tavern' room.
        # Try adding more player stats - level, gold, inventory, etc
        active_players[id] = {
            "name": "temp",
            "room": "temp",
            "inventory": []
        }

        # send the new player a prompt for their name
        mud.send_message(id,"What is your name?")

    # go through any recently disconnected players
    for id in mud.get_disconnected_players():

        # if for any reason the player isn't in the player map, skip them and
        # move on to the next one
        if id not in active_players: continue

        # go through all the players in the game
        for pid,pl in active_players.items():
            # send each player a message to tell them about the disconnected player
            mud.send_message(pid,"%s quit the game" % active_players[id]["name"])

        # remove the player's entry in the player dictionary
        del(active_players[id])

    # go through any new commands sent from players
    for id,command,params in mud.get_commands():

        # if for any reason the player isn't in the player map, skip them and
        # move on to the next one
        if id not in active_players:
            continue

        # if the player hasn't given their name yet, use this first command as their name
        if active_players[id]["name"] == "temp":

            active_players[id]["name"] = command
            active_players[id]["room"] = "Tavern"
            try:
                if players[command] is not None:
                    t_room = players[command]["room"]
                    t_inv = players[command]["inventory"]
                    active_players[id] = {"name": command, "room": t_room, "inventory": t_inv}
            except KeyError: pass

            # go through all the players in the game
            for pid,pl in active_players.items():
                # send each player a message to tell them about the new player
                mud.send_message(pid,"%s entered the game" % active_players[id]["name"])

            # send the new player a welcome message
            mud.send_message(id,"Welcome to the game, %s. Type 'help' for a list of commands."
                                " Have fun!" % active_players[id]["name"])

            # send the new player the description of their current room
            mud.send_message(id,rooms[active_players[id]["room"]]["description"])

        # each of the possible commands is handled below. Try adding new commands
        # to the game!
        else:
            command.lower()
            # 'help' command
            if command == "help":

                # send the player back the list of possible commands
                mud.send_message(id, "Commands:")
                mud.send_message(id, "  say <message>  - Says something out loud, e.g. 'say Hello'")
                mud.send_message(id, "  look           - Examines the surroundings, e.g. 'look'")
                mud.send_message(id, "  go <exit>      - Moves through the exit specified, e.g. 'go outside'")
                mud.send_message(id, "  room <name> <'Description.'> <exit>  - Creates a room with the given "
                                     "description and an exit to and from the given location.")

            # 'say' command
            elif command == "say":

                # go through every player in the game
                for pid,pl in active_players.items():
                    # if they're in the same room as the player
                    if active_players[pid]["room"] == active_players[id]["room"]:
                        # send them a message telling them what the player said
                        mud.send_message(pid,"%s says: %s" % (active_players[id]["name"],' '.join(params)) )

            # 'look' command
            elif command == "look":

                # store the player's current room
                rm = rooms[active_players[id]["room"]]

                # send the player back the description of their current room
                mud.send_message(id, rm["description"])

                playershere = []
                # go through every player in the game
                for pid,pl in active_players.items():
                    # if they're in the same room as the player
                    if active_players[pid]["room"] == active_players[id]["room"]:
                        # add their name to the list
                        if active_players[pid]["name"] is not None:
                            playershere.append(active_players[pid]["name"])

                print(len(playershere))
                # send player a message containing the list of players in the room
                if playershere is not None:
                    mud.send_message(id, "Players here: %s" % ", ".join(playershere))

                # send player a message containing the list of exits from this room
                mud.send_message(id, "Exits are: %s" % ", ".join(rm["exits"]))

            # 'go' command
            elif command == "go":

                # store the exit name
                ex = ' '.join(params)

                # store the player's current room
                rm = rooms[active_players[id]["room"]]

                # if the specified exit is found in the room's exits list
                if ex in rm["exits"]:

                    # go through all the players in the game
                    for pid,pl in active_players.items():
                        # if player is in the same room and isn't the player sending the command
                        if active_players[pid]["room"] == active_players[id]["room"] and pid!=id:
                            # send them a message telling them that the player left the room
                            mud.send_message(pid,"%s left via exit '%s'" % (active_players[id]["name"],ex))

                    # update the player's current room to the one the exit leads to
                    active_players[id]["room"] = rm["exits"][ex]
                    rm = rooms[active_players[id]["room"]]

                    # go through all the players in the game
                    for pid,pl in active_players.items():
                        # if player is in the same (new) room and isn't the player sending the command
                        if active_players[pid]["room"] == active_players[id]["room"] and pid!=id:
                            # send them a message telling them that the player entered the room
                            mud.send_message(pid,"%s arrived via exit '%s'" % (active_players[id]["name"],ex))

                    # send the player a message telling them where they are now
                    mud.send_message(id,"You arrive at '%s'" % active_players[id]["room"])

                # the specified exit wasn't found in the current room
                else:
                    # send back an 'unknown exit' message
                    mud.send_message(id, "Unknown exit '%s'" % ex)

            elif command == "room":

                rooms[params[0]] = {"description": params[1], "exits": {''.join(params[2]).lower(): params[2]}}
                rooms[params[2]]["exits"][params[0]] = params[0]

                with open('world.json', 'w') as outfile:
                    json.dump(rooms, outfile, sort_keys=True, indent=4, ensure_ascii=False)

            elif command == "stop":
                # go through all the players in the game
                for pid, pl in active_players.items():
                    # send each player a message to tell them about the disconnected player
                    mud.send_message(pid, "The server is shutting down! Bye!")

                save_players()

                print(players)
                with open('players.json', 'w') as outfile:
                    json.dump(players, outfile, sort_keys=True, indent=4, ensure_ascii=False)
                mud.shutdown()

            elif command == "give":
                it = ' '.join(params)
                active_players[id]["inventory"].append(it)

            # some other, unrecognised command
            else:
                # send back an 'unknown command' message
                mud.send_message(id, "Unknown command '%s'" % command)

        save_players()

    def save_players():

        for pid in active_players:
            t_name = active_players[pid]["name"]
            t_room = active_players[pid]["room"]
            t_inv = active_players[pid]["inventory"]
            players[t_name] = {"room": t_room, "inventory": t_inv}