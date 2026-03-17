class TopologicalMap:
    def __init__(self):
        # 1. 預先定義所有場站 (Locations)
        self.locations = {
            1:  "Living Room Table 1",
            2:  "Living Room Table 2",
            3:  "Living Room Sofa 1",
            4:  "Living Room Sofa 2",
            5:  "Living Room Cabinet",
            6:  "Kitchen Fridge",
            7:  "Kitchen Table 1",
            8:  "Kitchen Table 2",
            9:  "Room A Bed",
            10: "Room A Desk",
            11: "Room B Bed",
            12: "Room B Desk"
        }

        # 2. 初始化時間矩陣
        self.travel_times = {}
        for loc_id in self.locations.keys():
            self.travel_times[loc_id] = {}

        # 3. 載入拓樸地圖邊界 (Edges)
        self._load_map_data()

    def _add_edge(self, node1, node2, time_s):
        """將移動時間雙向寫入字典，確保查詢時 O(1) 的極速效能"""
        self.travel_times[node1][node2] = time_s
        self.travel_times[node2][node1] = time_s

    def _load_map_data(self):
        """載入您定義的所有移動時間 (自動雙向建立)"""
        edges = [
            # 1 開頭
            (1, 2, 40), (1, 3, 20), (1, 4, 50), (1, 5, 80), (1, 6, 490), 
            (1, 7, 440), (1, 8, 455), (1, 9, 380), (1, 10, 410), (1, 11, 595), (1, 12, 560),
            # 2 開頭
            (2, 3, 45), (2, 4, 15), (2, 5, 75), (2, 6, 485), (2, 7, 435), 
            (2, 8, 450), (2, 9, 375), (2, 10, 405), (2, 11, 590), (2, 12, 555),
            # 3 開頭
            (3, 4, 60), (3, 5, 60), (3, 6, 470), (3, 7, 420), (3, 8, 435), 
            (3, 9, 360), (3, 10, 390), (3, 11, 575), (3, 12, 540),
            # 4 開頭
            (4, 5, 60), (4, 6, 470), (4, 7, 420), (4, 8, 435), 
            (4, 9, 360), (4, 10, 390), (4, 11, 575), (4, 12, 540),
            # 5 開頭
            (5, 6, 410), (5, 7, 360), (5, 8, 375), (5, 9, 300), 
            (5, 10, 330), (5, 11, 515), (5, 12, 480),
            # 6 開頭
            (6, 7, 50), (6, 8, 40), (6, 9, 590), (6, 10, 620), (6, 11, 505), (6, 12, 470),
            # 7 開頭
            (7, 8, 15), (7, 9, 540), (7, 10, 570), (7, 11, 455), (7, 12, 420),
            # 8 開頭 (已修正 8-11 為 470)
            (8, 9, 555), (8, 10, 585), (8, 11, 470), (8, 12, 435),
            # 9 開頭
            (9, 10, 30), (9, 11, 395), (9, 12, 360),
            # 10 開頭
            (10, 11, 425), (10, 12, 390),
            # 11 開頭
            (11, 12, 35)
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

# === 測試區塊 ===
if __name__ == "__main__":
    topo = TopologicalMap()
    
    # 測試正常查詢
    print(f"從 '{topo.get_location_name(1)}' 到 '{topo.get_location_name(8)}' 需要: {topo.get_travel_time(1, 8)} 秒")
    
    # 測試雙向查詢 (確保 8 到 1 也是一樣的時間)
    print(f"從 '{topo.get_location_name(8)}' 到 '{topo.get_location_name(1)}' 需要: {topo.get_travel_time(8, 1)} 秒")
    
    # 測試原地不動
    print(f"從 '{topo.get_location_name(5)}' 到 '{topo.get_location_name(5)}' 需要: {topo.get_travel_time(5, 5)} 秒")