import random
import networkx as nx

import matplotlib.pyplot as plt

G = nx.Graph()
flow_table = {}

def compute_path(src, dst, priority, critical):
    global G
    try:
        paths = list(nx.shortest_simple_paths(G, src, dst))
    except nx.NetworkXNoPath:
        return None

    if not paths:
        return None

    if priority == True:
        return paths[0] # always choose shortest path
    else:
        # attempt to load balance non-priority flows
        def path_cost(path):
            return max(G[u][v]['num_flows'] for u, v in zip(path, path[1:]))
        return min(paths, key=path_cost)


def inject_flow(src, dst, priority, critical):
    # 1. Determine candidate paths
    # 2. Apply routing policy (shortest, priority, load-balancing)
    # 3. Choose one path
    # 4. Update flow_table
    # 5. Update G edge attributes (num_flows)
    # 6. Return or log result
    global G

    # compute paths
    path = compute_path(src, dst, priority, critical)
    backup_path = None
    if path == None:
        print(f"Failed to find a path for {src} {dst}")
        return
    if critical == True:
        backup_path = compute_backup_path(path)
    
    add_flow(src, dst, path, priority, critical, backup_path)
    # if paths are equal, select path with fewest flows for load balancing

def compute_backup_path(primary_path):
    global G
    G_copy = G.copy()
    # Remove edges in primary path
    for u, v in zip(primary_path, primary_path[1:]):
        if G_copy.has_edge(u, v):
            G_copy.remove_edge(u, v)

    try:
        # Try to find alternate route in modified graph
        return nx.shortest_path(G_copy, primary_path[0], primary_path[-1])
    except nx.NetworkXNoPath:
        return None

def add_flow(src, dst, path, priority, critical, backup_path=None):
    global G, flow_table

    # Update flow table
    flow_table[(src, dst)] = {
        'priority': priority,
        'critical': critical,
        'primary': path,
        'backup': backup_path,
        'active': 'primary'
    }

    # Increment num_flows on each edge in the path
    for u, v in zip(path, path[1:]):
        if G.has_edge(u, v):
            G[u][v]['num_flows'] += 1

def remove_flow(src, dst):
    global G, flow_table

    key = (src, dst)
    if key not in flow_table:
        print(f"No active flow from {src} to {dst} to remove.")
        return

    flow = flow_table[key]
    path = flow.get(flow['active'], [])

    # Decrement flow counts on each edge
    for u, v in zip(path, path[1:]):
        if G.has_edge(u, v):
            G[u][v]['num_flows'] = max(0, G[u][v]['num_flows'] - 1)

    # Remove flow from table
    del flow_table[key]
    print(f"Flow from {src} to {dst} removed.")

def fail_link(u, v):
    global G, flow_table

    if not G.has_edge(u, v):
        print(f"No link between {u} and {v} exists.")
        return

    print(f"Failing link: {u} - {v}")
    G.remove_edge(u, v)

    affected_flows = []
    for (src, dst), info in list(flow_table.items()):
        path = info.get(info['active'], [])
        if path and (u, v) in zip(path, path[1:]) or (v, u) in zip(path, path[1:]):
            affected_flows.append((src, dst, info))

    for src, dst, info in affected_flows:
        print(f"Flow from {src} to {dst} affected by failure.")

        # Decrement old path
        old_path = info.get(info['active'], [])
        for x, y in zip(old_path, old_path[1:]):
            if G.has_edge(x, y):  # in case of multiple failures
                G[x][y]['num_flows'] = max(0, G[x][y]['num_flows'] - 1)

        if info['critical'] == True and info['backup']:
            # Promote backup to primary
            new_path = info['backup']
            for x, y in zip(new_path, new_path[1:]):
                if G.has_edge(x, y):
                    G[x][y]['num_flows'] += 1
            flow_table[(src, dst)]['active'] = 'backup'
            print(f"→ Rerouted {src}->{dst} to backup path: {new_path}")
        else:
            # Remove flow entirely
            del flow_table[(src, dst)]
            print(f"→ Flow {src}->{dst} removed (no backup available)")

def draw_topology(G):
    plt.clf()
    pos = nx.spring_layout(G)
    nx.draw(G, pos, with_labels=True, node_color='skyblue', edge_color='gray')
    edge_labels = nx.get_edge_attributes(G, 'num_flows')
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels)
    plt.pause(0.5)  # pause to update the plot

def main():
    
    # set up initial topology state
    global G

    G.add_node('A')
    G.add_node('B')
    G.add_node('C')
    G.add_node('D')
    G.add_node('E')
    G.add_edge('A', 'C', num_flows = 0)
    G.add_edge('A', 'E', num_flows = 0)
    G.add_edge('B', 'E', num_flows = 0)
    G.add_edge('C', 'E', num_flows = 0)
    G.add_edge('D', 'E', num_flows = 0)
    inject_flow('A', 'B', False, False)
    inject_flow('A', 'C', False, True)
    inject_flow('B', 'C', True, False)

    draw_topology(G)

    # command loop
    while True:
        cmd = input("<SDN>:")
        cmd = cmd.split(" ")
        if cmd[0] == "insert_link":
            if len(cmd) != 3:
                print("Incorrect number of arguments")
            elif G.has_node(cmd[1]) and G.has_node(cmd[2]):
                if G.has_edge(cmd[1], cmd[2]):
                    print("link already exists")
                else:
                    G.add_edge(cmd[1], cmd[2], num_flows = 0)
                    print("Added edge "+cmd[1]+cmd[2])
            else:
                print("1 or more nodes not in network")
        elif cmd[0] == "insert_node":
            if len(cmd) != 2:
                print("Incorrect number of arguments")
            elif G.has_node(cmd[1]):
                print("Node already exists")
            else:
                G.add_node(cmd[1])
                print(f"Node {cmd[1]} added")
        elif cmd[0] == "delete_node:":
            if len(cmd) != 2:
                print("Incorrect number of arguments")
            elif G.has_node(cmd[1]):
                G.remove_node(cmd[1])
                print("Removed node "+cmd[1]+" from the network.")
        elif cmd[0] == "inject":
            if len(cmd) != 5:
                print("Incorrect number of arguments")
            else:
                src, dst = cmd[1], cmd[2]
                try:
                    priority = bool(int(cmd[3]))
                    critical = bool(int(cmd[4]))
                    inject_flow(src, dst, priority, critical)
                except ValueError:
                    print("Priority and critical must be 0 or 1")
        elif cmd[0] == "disable" or cmd[0] == "delete_link":
            if len(cmd) != 3:
                print("Incorrect number of arguments")
            else:
                fail_link(cmd[1], cmd[2])
        elif cmd[0] == "query":
            if len(cmd) != 3:
                print("Incorrect number of arguments")
            else:
                key = (cmd[1], cmd[2])
                if key in flow_table:
                    f = flow_table[key]
                    print(f"Flow {key} | Active: {f['active']} | Primary: {f['primary']} | Backup: {f['backup']}")
                else:
                    print(f"No flow found from {cmd[1]} to {cmd[2]}")
        elif cmd[0] == "quit":
            break
        else:
            print("Unknown command issued")
        #hash: 0580c681b5c692ab7b85680dfe8ec791bdd83a16786b325d598dcc74edb06ce7
        draw_topology(G)

main()

"""
paths = list(nx.all_simple_paths(G, 'A', 'D'))
shortest_len = min(len(p) for p in paths)
shortest_paths = [p for p in paths if len(p) == shortest_len]
"""