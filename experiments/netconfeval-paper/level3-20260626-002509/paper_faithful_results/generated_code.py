from collections import defaultdict, deque
from typing import Dict, List, Optional

def compute_routing_paths(topology: Dict[str, Dict[int, str]], network_requirements: Optional[None] = None) -> Dict[str, Dict[str, List[str]]]:
    # EN: Build a graph as an adjacency list over LAN-connected devices.
    # CN: 将图构造成按 LAN 相连的设备邻接表。
    # EN: Group devices by LAN first.
    # CN: 先按 LAN 分组设备。
    lan_to_devices = defaultdict(list)
    for device, ports in topology.items():
        for port, lan in ports.items():
            lan_to_devices[lan].append(device)

    # EN: Connect every device within the same LAN.
    # CN: 将同一 LAN 内的设备全部连接。
    adj = defaultdict(set)
    for lan, devices in lan_to_devices.items():
        for i in range(len(devices)):
            for j in range(i+1, len(devices)):
                d1 = devices[i]
                d2 = devices[j]
                adj[d1].add(d2)
                adj[d2].add(d1)

    # EN: Keep hosts only; names start with `h`.
    # CN: 只保留主机；名称以 `h` 开头。
    hosts = [device for device in topology if device.startswith('h')]

    # EN: Compute shortest paths to other hosts with BFS.
    # CN: 用 BFS 计算到其他主机的最短路径。
    paths_dict = {}
    for src in hosts:
        # EN: BFS from src to all other nodes.
        # CN: 从 src 对所有节点做 BFS。
        visited = {src}
        queue = deque([(src, [src])])
        paths = {}
        while queue:
            current, path = queue.popleft()
            if current.startswith('h') and current != src:
                paths[current] = path
            for neighbor in adj[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        if paths:
            paths_dict[src] = paths

    return paths_dict
