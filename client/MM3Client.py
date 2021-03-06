from smart_m3.m3_kp import *
import uuid
import re
import sys
from termcolor import colored
sys.path.append("../")
from sib import SIBLib
import time
from client_query import *
# handlers
from turn_handler import TurnHandler
from change_position_handler import ChangePositionHandler
from change_balance_handler import ChangeBalanceHandler
from contract_handler import ContractHandler
from number_of_houses_handler import NumberOfHousesHandler
from lost_game_handler import LostGameHandler
import threading

rdf = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
owl = "http://www.w3.org/2002/07/owl#"
xsd = "http://www.w3.org/2001/XMLSchema#"
rdfs = "http://www.w3.org/2000/01/rdf-schema#"
ns = "http://smartM3Lab/Ontology.owl#"

class MM3Client:

    def __init__(self, ip, port, debug, gtki, interface):
        try:
            # client info
            self.gtki = gtki
            self.interface = interface            

            # connection to the sib
            self.node = SIBLib.SibLib(ip, port)
            self.node.join_sib()
            
            # player info
            self.current_position = None
            self.nickname = None
            self.balance = 1000
            self.game_session = None
            self.turn_number = 0
            self.role = None
            self.waiting = False
    
            self.sem_lock = False
            self.semaphore = threading.Lock()
            self.last_command = None
            self.heading = colored("MM3Client> ", "red", attrs=["bold"])
            
            # board info
            self.properties = []
            for i in range(0,38):
                self.properties.append({})

            print colored("MM3Client>", "red", attrs=["bold"]) + " connected!"
            
        except Exception as e:
            print colored("MM3Client>", "red", attrs=["bold"]) + " Exception while starting the client, aborting!"
            sys.exit(0)

    def lock(self, who):
        if self.sem_lock is False:
            try:
                self.semaphore.acquire()
            except Exception:
                pass
            finally:
                self.sem_lock = True

    def unlock(self, who):
        if self.sem_lock is False: 
            try:
                self.semaphore.release()
            except Exception:
                pass
            finally:
                self.sem_lock = False

    def get_game_session_list(self):

        # query to select available sessions
        query = """
        SELECT ?s
        WHERE {?s ns:HasStatus ns:Waiting}
        """
        result = self.node.execute_query(query)

        game_session_list = []
        for i in result:
            game_session_list.append(str(i[0][2].split('#')[1]))
          
        return game_session_list

    def join_game_session(self, gamesession, role, nickname):
        try:

            # set the role
            self.role = role

            # set the gamesession
            self.game_session = gamesession

            # declare the client as a player or as an observer
            triples = []
            if (role == "player"):

                # get players number for the current session
                temp = []
                query = """
                     SELECT ?s ?o
                     WHERE { ns:""" + gamesession + """ ns:numberOfPlayers ?o}          
                     """

                result = self.node.execute_query(query)
                for i in result:
                    for j in i:
                        for k in j:
                            temp.append(k)

                cont_players=int(temp[5].split('#')[1])
                cont_players+=1
    
                # is nickname already registered?
                player_list = []
                query = """SELECT ?p 
                WHERE {ns:""" + str(gamesession) + """ ns:HasPlayer ?p}"""
                result = self.node.execute_query(query)
                if (len(result) > 0):
                    for pl in result:
                        player_list.append(pl[0][2].split('#')[1])
                
                # controllo se il nick e' gia' presente (parte testuale)
                valid = False
                reg = re.compile(r"[a-zA-Z0-9_]*$")
                if not(self.gtki):
                    while (valid == False):
                        nickname_gs = nickname + "_" + str(gamesession) 
                        if (nickname_gs in player_list):
                            print "Nickname already in use!"                        
                            nickname = raw_input("Insert another nickname > ")
                            while not(reg.match(nickname)):
                                print "Nickname not valid!"
                                nickname = raw_input("Insert another nickname > ")
                        else:
                            valid = True
	    
	                        
                               
                # controllo se il nick e' gia' presente (dall'interfaccia grafica)
                else:
                    while (valid == False):
                        nickname = self.interface.nickname_entry.get()
                        nickname_gs = nickname + "_" + str(gamesession) 
                        if (nickname_gs in player_list):
                            self.interface.error_label.config(text = "Nickname already in use! Insert another one!", fg = "red")
                            self.interface.nickname_entry.delete(0, END)
                        else:
                            valid = True
                    
                self.nickname = nickname_gs
                
                #self.nickname = "player_" + str(cont_players)
    
                # add the player

                # declare the client as a Person
                triples.append(Triple(URI(ns + self.nickname),
                                      URI(rdf + "type"),
                                      URI(ns + "Person")))
                triples.append(Triple(URI(ns + gamesession),
                                      URI(ns + "HasPlayer"),
                                      URI(ns + self.nickname)))
                
                # insert the triples into the sib
                self.node.insert(triples)
                
                # update players number in the sib
                it = []
                dt = []
                it.append(Triple(URI(ns + gamesession),
                                 URI(ns + "numberOfPlayers"),
                                 URI(ns + str(cont_players))))
                                
                dt.append(Triple(URI(ns + gamesession),
                                 URI(ns + "numberOfPlayers"),
                                 URI(ns + str(cont_players - 1))))
            
                self.node.update(it,dt)

                # set the initial position of the player
                triples = []
                triples.append(Triple(URI(ns + self.nickname),
                                      URI(ns + "IsInBox"),
                                      URI(ns + '0')))
                self.current_position = 0

                # set the initial money balance
                triples.append(Triple(URI(ns + self.nickname),
                                      URI(ns + "cashBalance"),
                                      URI(ns + "1000")))
                
                triples.append(Triple(URI(ns + self.nickname),
                                      URI(ns + "userID"),
                                      URI(ns + str(cont_players))))

                # insert the triples into the sib
                self.node.insert(triples)
                self.game_session = gamesession
                
            elif (role == "observer"):
                self.nickname = nickname + "_" + str(gamesession)
                triples.append(Triple(URI(ns + gamesession),
                                      URI(ns + "HasObserver"),
                                      URI(ns + self.nickname)))
                # insert the triples into the sib
                self.node.insert(triples)

        except():
            print colored("MM3Client> ", 'red', attrs=['bold']) + " an exception occurred during the player registration.. aborting!"
            sys.exit(0)

    def launch_subscriptions(self):
        
        # first sub
        triple_turn = Triple(URI(ns + self.game_session),
                        URI(ns + "TurnOf"),
                        None)
        
        print colored("MM3Client> ", 'red', attrs=['bold']) + "new subscription for the turn"        
        self.st1 = self.node.CreateSubscribeTransaction(self.node.ss_handle)
        initial_results1 = self.st1.subscribe_rdf(triple_turn, TurnHandler(self))

        # second sub
        triple_turn = Triple(None,
                        URI(ns + "IsInBox"),
                        None)

        print colored("MM3Client> ", 'red', attrs=['bold']) + "new subscription for the position"        
        self.st2 = self.node.CreateSubscribeTransaction(self.node.ss_handle)
        initial_results2 = self.st2.subscribe_rdf(triple_turn,
            ChangePositionHandler(self))

        # third sub
        triple_balance = Triple(None,
                                URI(ns + "cashBalance"),
                                None)

        print colored("MM3Client> ", 'red', attrs=['bold']) + "new subscription for the cash balance"        
        self.st3 = self.node.CreateSubscribeTransaction(self.node.ss_handle)
        initial_results3 = self.st3.subscribe_rdf(triple_balance, ChangeBalanceHandler(self))

        # fourth sub
        triple_contracts = Triple(None,
                        URI(ns + "HasContract"),
                        None)

        print colored("MM3Client> ", 'red', attrs=['bold']) + "new subscription for the contracts"        
        self.st4 = self.node.CreateSubscribeTransaction(self.node.ss_handle)
        initial_results4 = self.st4.subscribe_rdf(triple_contracts, ContractHandler(self))

        # fifth sub
        triple_houses = Triple(None,
                        URI(ns + "numberOfHouses"),
                        None)

        print colored("MM3Client> ", 'red', attrs=['bold']) + "new subscription for the houses"        
        self.st5 = self.node.CreateSubscribeTransaction(self.node.ss_handle)
        initial_results5 = self.st5.subscribe_rdf(triple_houses, NumberOfHousesHandler(self))

        # sixth sub
        triple_lost = Triple(URI(ns + self.game_session),
                             URI(ns + "HasStatus"),
                             URI(ns + "Ended"))

        print colored("MM3Client> ", 'red', attrs=['bold']) + "new subscription for the end of the game"
        self.st6 = self.node.CreateSubscribeTransaction(self.node.ss_handle)
        initial_results6 = self.st6.subscribe_rdf(triple_lost, LostGameHandler(self))
        

    def close_subscriptions(self):
        # closing subscriptions
        print colored("MM3Client> ", 'red', attrs=['bold']) + "closing subscriptions..."
        self.node.CloseSubscribeTransaction(self.st1)
        self.node.CloseSubscribeTransaction(self.st2)
        self.node.CloseSubscribeTransaction(self.st3)
        self.node.CloseSubscribeTransaction(self.st4)
        self.node.CloseSubscribeTransaction(self.st5)
        self.node.CloseSubscribeTransaction(self.st6)
        
    def leave_sib(self):
        # leaving the sib
        print colored("MM3Client> ", 'red', attrs=['bold']) + "leaving the sib..."
        self.node.leave_sib()
    
    def clear_my_sib(self):
        print colored("MM3Client> ", 'red', attrs=['bold']) + "cleaning the sib..."
        # removing all the triples with the loser as the subject
        query = """SELECT ?p ?o WHERE { ns:""" + self.nickname + """ ?p ?o }"""
        s_result = self.node.execute_query(query)
            
        s_triples = []
        for c in s_result:
            s_triples.append(Triple(URI(ns + self.nickname), URI(c[0][2]), URI(c[1][2])))
            self.node.remove(s_triples)

            # removing all the triples with the loser as the object
            query = """SELECT ?s ?p WHERE { ?s ?p ns:""" + self.nickname + """}"""
            o_result = self.node.execute_query(query)
            
            o_triples = []
            for c in o_result:
                o_triples.append(Triple(URI(c[0][2]), URI(c[1][2]), URI(ns + self.nickname)))
            self.node.remove(o_triples)

    def begin_observer(self):
        # inserting a triple to let the old player observe the rest of the game
        obs_triple = [(Triple(URI(ns + self.game_session), URI(ns + "HasObserver"),
            URI(ns + self.nickname)))]
        self.node.insert(obs_triple)
        self.role = "observer"
        print self.heading + "now you observe the rest of the match"

