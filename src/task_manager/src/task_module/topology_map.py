import heapq
import os

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib import animation


class TopologicalMap:
    def __init__(self):
        # 1. 預先定義所有場站 (20 個居家場景)
        self.locations = {
            1: "tv_cabinet",
            2: "coffee_table",
            3: "small_round_side_table",
            4: "dining_table",
            5: "bar_counter",
            6: "snack_cabinet",
            7: "fridge",
            8: "sink_counter",
            9: "stove_side_counter",
            10: "cabinet",
            11: "master_bedside_table",
            12: "master_vanity",
            13: "master_desk",
            14: "guest_bedside_table",
            15: "guest_desk",
            16: "study_computer_desk",
            17: "bookshelf",
            18: "entry_shoe_cabinet",
            19: "hallway_storage_cabinet",
            20: "water_dispenser",
        }

        # 2. 視覺化固定座標 (讓畫面更像居家平面圖，不用每次 spring 亂排)
        self.plot_positions = {
            1: (8.6, 4.2),
            2: (7.0, 4.4),
            3: (7.8, 3.6),
            4: (7.9, 5.8),
            5: (7.2, 5.8),
            6: (8.6, 5.1),
            7: (7.9, 7.0),
            8: (7.1, 7.0),
            9: (6.3, 7.0),
            10: (5.8, 4.1),
            11: (4.8, 4.4),
            12: (4.0, 4.9),
            13: (3.2, 3.9),
            14: (4.8, 5.9),
            15: (4.0, 5.9),
            16: (5.8, 3.2),
            17: (5.0, 3.2),
            18: (9.4, 3.3),
            19: (6.5, 4.1),
            20: (7.55, 6.55),
        }

        # 3. 初始化時間矩陣
        self.travel_times = {}
        for loc_id in self.locations.keys():
            self.travel_times[loc_id] = {}

        # 4. 載入拓樸地圖邊界 (Edges)
        self._load_map_data()

    def _add_edge(self, node1, node2, time_s):
        """將移動時間雙向寫入字典，確保查詢時 O(1) 的極速效能"""
        self.travel_times[node1][node2] = time_s
        self.travel_times[node2][node1] = time_s

    def _load_map_data(self):
        """載入相鄰節點移動時間 (秒)，由 Dijkstra 求最短路徑"""
        edges = [
            # 客廳 / 玄關 / 餐廳
            (18, 1, 25),
            (18, 6, 30),
            (1, 2, 30),
            (2, 3, 35),
            (4, 1, 60),
            (2, 5, 60),
            (4, 5, 20),
            (4, 6, 28),
            (4, 20, 40),
            (5, 20, 30),
            # 廚房
            (5, 8, 35),
            (8, 9, 25),
            (8, 7, 20),
            # 走廊連到各房間
            (2, 19, 40),
            (5, 19, 45),
            (19, 10, 15),
            (19, 11, 180),
            (19, 16, 140),
            (11, 12, 45),
            (11, 13, 25),
            (19, 14, 110),
            (14, 15, 20),
            (11, 16, 110),
            (16, 17, 35),
        ]
        
        for u, v, t in edges:
            self._add_edge(u, v, t)

    def get_location_name(self, loc_id):
        """輸入場站 ID，回傳場站英文名稱"""
        return self.locations.get(loc_id, f"Unknown Location ({loc_id})")

    def get_travel_time(self, start_id, end_id):
        """獲取兩點之間的移動時間"""
        # 如果原地不動，時間為 0
        if start_id == end_id:
            return 0
            
        # 查詢時間
        if end_id in self.travel_times.get(start_id, {}):
            return self.travel_times[start_id][end_id]
        else:
            print(f"[警告] 找不到地點 {start_id} 到 {end_id} 的移動時間！")
            return float('inf')

    def get_shortest_path(self, start_id, end_id):
        """使用 Dijkstra 計算最短路徑，回傳 (path_ids, total_time)"""
        if start_id not in self.locations or end_id not in self.locations:
            print(f"[警告] 無效地點 ID: start={start_id}, end={end_id}")
            return [], float('inf')

        if start_id == end_id:
            return [start_id], 0

        distances = {node: float('inf') for node in self.locations}
        previous = {node: None for node in self.locations}
        distances[start_id] = 0

        pq = [(0, start_id)]

        while pq:
            cur_dist, cur_node = heapq.heappop(pq)

            if cur_dist > distances[cur_node]:
                continue

            if cur_node == end_id:
                break

            for neighbor, weight in self.travel_times.get(cur_node, {}).items():
                new_dist = cur_dist + weight
                if new_dist < distances[neighbor]:
                    distances[neighbor] = new_dist
                    previous[neighbor] = cur_node
                    heapq.heappush(pq, (new_dist, neighbor))

        if distances[end_id] == float('inf'):
            print(f"[警告] 找不到從 {start_id} 到 {end_id} 的可達路徑！")
            return [], float('inf')

        # 回溯路徑
        path = []
        node = end_id
        while node is not None:
            path.append(node)
            node = previous[node]
        path.reverse()

        return path, distances[end_id]

    def get_shortest_path_with_names(self, start_id, end_id):
        """回傳 (path_ids, path_names, total_time) 方便直接印出結果"""
        path_ids, total_time = self.get_shortest_path(start_id, end_id)
        path_names = [self.get_location_name(pid) for pid in path_ids]
        return path_ids, path_names, total_time

    def _build_nx_graph(self):
        """將目前拓樸資料轉成 networkx 圖結構"""
        graph = nx.Graph()

        for loc_id, loc_name in self.locations.items():
            graph.add_node(loc_id, label=loc_name)

        # travel_times 是雙向儲存，這裡只加一次邊
        for u, neighbors in self.travel_times.items():
            for v, weight in neighbors.items():
                if u < v:
                    graph.add_edge(u, v, weight=weight)

        return graph

    def _get_plot_positions(self, graph):
        """優先使用固定座標，缺漏時回退 spring layout"""
        if all(n in self.plot_positions for n in graph.nodes):
            return {n: self.plot_positions[n] for n in graph.nodes}
        return nx.spring_layout(graph, seed=42)

    def export_path_visuals(self, start_id, end_id, output_dir):
        """輸出靜態 PNG 與路徑動畫 GIF/MP4"""
        os.makedirs(output_dir, exist_ok=True)

        path_ids, path_names, total_time = self.get_shortest_path_with_names(start_id, end_id)
        if not path_ids:
            print("[警告] 無法輸出圖像，因為沒有可用路徑。")
            return None

        graph = self._build_nx_graph()
        pos = self._get_plot_positions(graph)
        path_edges = list(zip(path_ids, path_ids[1:]))

        png_path = os.path.join(output_dir, "topology_map.png")
        plain_png_path = os.path.join(output_dir, "topology_map_plain.png")
        gif_path = os.path.join(output_dir, "topology_map.gif")
        mp4_path = os.path.join(output_dir, "topology_map.mp4")

        # 0) 純拓樸圖（不標記任何最短路徑）
        fig, ax = plt.subplots(figsize=(12, 8))
        labels = {n: f"{n}\n{self.locations[n]}" for n in graph.nodes}
        edge_labels = nx.get_edge_attributes(graph, "weight")

        nx.draw_networkx_nodes(graph, pos, node_color="#d9ecff", node_size=1500, ax=ax)
        nx.draw_networkx_edges(graph, pos, edge_color="#c0c0c0", width=1.2, ax=ax)
        nx.draw_networkx_labels(graph, pos, labels=labels, font_size=8, ax=ax)
        nx.draw_networkx_edge_labels(
            graph,
            pos,
            edge_labels=edge_labels,
            font_size=7,
            font_color="#0b3d91",
            bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none", "pad": 0.2},
            ax=ax,
        )
        ax.set_title("Topological Map (No Route Highlight)", fontsize=11)
        ax.axis("off")
        fig.tight_layout()
        fig.savefig(plain_png_path, dpi=200, bbox_inches="tight")
        plt.close(fig)
        print(f"[OK] Plain topology map saved: {plain_png_path}")

        # 1) 靜態圖輸出
        fig, ax = plt.subplots(figsize=(12, 8))

        nx.draw_networkx_nodes(graph, pos, node_color="#d9ecff", node_size=1500, ax=ax)
        nx.draw_networkx_edges(graph, pos, edge_color="#c0c0c0", width=1.2, ax=ax)
        nx.draw_networkx_labels(graph, pos, labels=labels, font_size=8, ax=ax)
        nx.draw_networkx_edge_labels(
            graph,
            pos,
            edge_labels=edge_labels,
            font_size=7,
            font_color="#0b3d91",
            bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none", "pad": 0.2},
            ax=ax,
        )

        if path_edges:
            nx.draw_networkx_edges(
                graph,
                pos,
                edgelist=path_edges,
                edge_color="red",
                width=3.0,
                ax=ax,
            )
            nx.draw_networkx_nodes(
                graph,
                pos,
                nodelist=path_ids,
                node_color="#ffb3b3",
                node_size=1700,
                ax=ax,
            )

        ax.set_title(
            f"Topological Map\nShortest path: {' -> '.join(path_names)} | total: {total_time}s",
            fontsize=11,
        )
        ax.axis("off")
        fig.tight_layout()
        fig.savefig(png_path, dpi=200, bbox_inches="tight")
        plt.close(fig)
        print(f"[OK] Static map saved: {png_path}")

        # 2) 動畫輸出 (GIF / MP4)
        fig, ax = plt.subplots(figsize=(12, 8))
        nx.draw_networkx_nodes(graph, pos, node_color="#d9ecff", node_size=1500, ax=ax)
        nx.draw_networkx_edges(graph, pos, edge_color="#c0c0c0", width=1.2, ax=ax)
        nx.draw_networkx_labels(graph, pos, labels=labels, font_size=8, ax=ax)
        nx.draw_networkx_edge_labels(
            graph,
            pos,
            edge_labels=edge_labels,
            font_size=7,
            font_color="#0b3d91",
            bbox={"facecolor": "white", "alpha": 0.75, "edgecolor": "none", "pad": 0.2},
            ax=ax,
        )

        if path_edges:
            nx.draw_networkx_edges(
                graph,
                pos,
                edgelist=path_edges,
                edge_color="red",
                width=3.0,
                ax=ax,
            )

        ax.set_title("Robot Path Animation", fontsize=11)
        ax.axis("off")

        # 將每一段邊插值為多個 frame，讓機器人移動更平滑
        frame_points = []
        if len(path_ids) == 1:
            frame_points.append(pos[path_ids[0]])
        else:
            frames_per_segment = 16
            for i in range(len(path_ids) - 1):
                x1, y1 = pos[path_ids[i]]
                x2, y2 = pos[path_ids[i + 1]]
                for k in range(frames_per_segment):
                    t = k / float(frames_per_segment)
                    frame_points.append((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t))
            frame_points.append(pos[path_ids[-1]])

        robot_dot, = ax.plot([], [], "o", color="#ff2d2d", markersize=12)

        def _init():
            x0, y0 = frame_points[0]
            robot_dot.set_data([x0], [y0])
            return (robot_dot,)

        def _update(frame_idx):
            x, y = frame_points[frame_idx]
            robot_dot.set_data([x], [y])
            return (robot_dot,)

        anim = animation.FuncAnimation(
            fig,
            _update,
            init_func=_init,
            frames=len(frame_points),
            interval=120,
            blit=True,
            repeat=False,
        )

        # GIF 使用 pillow writer，通常最穩定
        anim.save(gif_path, writer=animation.PillowWriter(fps=8))
        print(f"[OK] GIF animation saved: {gif_path}")

        # MP4 需要 ffmpeg；若不可用則跳過
        try:
            anim.save(mp4_path, writer=animation.FFMpegWriter(fps=8, bitrate=1800))
            print(f"[OK] MP4 animation saved: {mp4_path}")
        except Exception as e:
            print(f"[WARN] MP4 export skipped (ffmpeg may be unavailable): {e}")

        plt.close(fig)

        return {
            "png": png_path,
            "plain_png": plain_png_path,
            "gif": gif_path,
            "mp4": mp4_path,
            "path_ids": path_ids,
            "total_time": total_time,
        }

# === 測試區塊 ===
if __name__ == "__main__":
    topo = TopologicalMap()
    
    # 測試相鄰查詢
    print(f"從 '{topo.get_location_name(1)}' 到 '{topo.get_location_name(2)}' 需要: {topo.get_travel_time(1, 2)} 秒")
    
    # 測試雙向查詢 (確保 2 到 1 也是一樣的時間)
    print(f"從 '{topo.get_location_name(2)}' 到 '{topo.get_location_name(1)}' 需要: {topo.get_travel_time(2, 1)} 秒")
    
    # 測試原地不動
    print(f"從 '{topo.get_location_name(5)}' 到 '{topo.get_location_name(5)}' 需要: {topo.get_travel_time(5, 5)} 秒")

    # 測試非相鄰點的最短路徑
    start_id, end_id = 9, 16
    path_ids, path_names, total_time = topo.get_shortest_path_with_names(start_id, end_id)
    print(f"最短路徑 ID: {path_ids}")
    print(f"最短路徑名稱: {' -> '.join(path_names)}")
    print(f"最短路徑總時間: {total_time} 秒")

    # 匯出靜態圖與動畫
    output_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../output")
    )
    topo.export_path_visuals(start_id, end_id, output_dir)