README
=======================
GBN + Distance Vector Routing Algorithm
Emily Soto at Columbia University, Computer Networks

             ,----------------,              ,---------,
        ,-----------------------,          ,"        ,"|
      ,"                      ,"|        ,"        ,"  |
     +-----------------------+  |      ,"        ,"    |
     |  .-----------------.  |  |     +---------+      |
     |  |                 |  |  |     | -==----'|      |
     |  |  NETWORKS       |  |  |     |         |      |
     |  |     PA2         |  |  |/----|`---=    |      |
     |  |  C:\>_          |  |  |   ,/|==== ooo |      ;
     |  |                 |  |  |  // |(((( [33]|    ,"
     |  `-----------------'  |," .;'| |((((     |  ,"
     +-----------------------+  ;;  | |         |,"
        /_)______________(_/  //'   | +---------+
   ___________________________/___  `,
  /  oooooooooooooooo  .o.  oooo /,   \,"-----------
 / ==ooooooooooooooo==.o.  ooo= //   ,`\--{)B     ,"
/_==__==========__==_ooo__ooo=_/'   /___________,"
`-----------------------------'


GBNNODE
===========

INSTRUCTIONS:
    python gbnnode.py <local_port> <peer_port> <window_size> [-p|-d]

OPTIONAL ARGS:
    -p : probabilistic drop rate, enter the probability of a packet being dropped in decimal format
    -d : deterministic drop rate, enter the repeating interval in which you want one packet to be dropped as an integer

NOTES:
  Messages are strings separated into single character packets with a sequence number, data, "sent" flag, and a type indicator
  differentiating between ACKs, EOTs, and Data-carrying packets.

  At the end of each message, an EOT packet is sent out to signal to the receiver that no more packets are expected.
  The receiver sends a final ACK in response, verifying that it got the EOT packet, which has "EOT" in its data field.
  It then prints out a summary detailing the drop rate of ACKs and resets its state.

  When the sender receives this final ACK, which already has information about the message length, gives a summary of the
  packets lost vs. packets transmitted ratio and then resets its state as well.

  Exit using Ctrl + C.

**DVNODE**
===========
Eventually, routing tables should converge to expected

Instructions: For each node
    python dvnode.py <local-port> <neighbor1-port> <loss-rate-1> <neighbor2-port> <loss-rate-2> ... [last]

OPTIONAL ARGS:
    last : if final arg, will send routing message out and the Bellman-Ford algorithm should start

NOTES:
There are no one way connections: if a node has a given peer node in a routing table, then the peer node must also have that node in its own routing table
when passing in the command line arguments. Implemented with a dictionary routing table with tuple values holding the distance and ports of its neighbors.
Each node only has access to its immediate neighbors and rely on their updates to "know" about indirectly connected nodes.

Exit using Ctrl + C

  **CNNODE**
============
Instructions: For each node
    python cnnode.py <local-port> receive <neighbor1-port> <loss-rate-1> <neighbor2-port> <loss-rate-2> ... <neighborM-port>
<loss-rate-M> send <neighbor(M+100)-port> <neighbor(M+200)-port> ... <neighborN-port> [last]

!! IMPORTANT!!
 PROVIDED PORT #S MUST BE AT LEAST 100 APART. THE FURTHER APART THE BETTER.

Notes:
A combination of the Distance-Vector Routing Algorithm and Go Back N. Probing packets are sent out periodically to calculate a loss rate, which is then
interpreted as the distance between routers. Subclasses DVNode and utilizes GBNNodes to send and receive probes on links.

Notably, due to the speed of updates, the output can be particularly difficult to see. I recommend using Ctrl + C to get a clear look at the routing
table once you're done waiting for it to converge.

Exit using Ctrl + C