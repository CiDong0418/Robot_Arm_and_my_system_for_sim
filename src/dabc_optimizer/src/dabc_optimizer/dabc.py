import random
import copy
import math
from .fitness import TaskScheduler

class DABC:
    def __init__(self, task_lookup, population_size=20, max_iterations=100, limit=20, initial_seq=None):
        
        self.task_ids = list(task_lookup.keys())
        self.scheduler = TaskScheduler(task_lookup)
        self.pop_size = population_size  # 族群大小
        self.max_iter = max_iterations 
        self.limit = limit  # 偵查蜂重複次數限制 如果一個解連續 limit 次沒變好，就放棄它
        
        
        self.population = [] # 存解
        self.fitness_values = [] # 存適應值
        self.trial_counters = [] # 存 沒有 進步次數

        for i in range(self.pop_size):
            if i == 0 and initial_seq is not None:
                # 如果有提供初始解，第一個解就用它
                individual = copy.deepcopy(initial_seq)
                llm_fit = self.scheduler.calculate_makespan(individual)
                print(f"==========================================")
                print(f"🐝 [Baseline] 第 1 隻蜜蜂 (LLM 全域排程) 初始成績: {llm_fit} 秒")
                print(f"==========================================")

            # individual = copy.deepcopy(self.task_ids)
            # random.shuffle(individual)
            # self.population.append(individual)
            else:
                # 剩下的 9 隻蜜蜂
                individual = self._generate_topological_individual()
            
            self.population.append(individual)
            # 計算適應值
            fit = self.scheduler.calculate_makespan(individual)
            self.fitness_values.append(fit)   # 存放適應值
            self.trial_counters.append(0) # 初始化計數器為 0 紀錄每一個解沒有進步的次數


        # 紀錄全域最佳解
        self.global_best_sol = None
        self.global_best_fit = float('inf')
        self._update_global_best()

    def optimize(self):
        """執行完整版 DABC 迭代"""
        
        for iteration in range(self.max_iter):
            # 1. 雇工蜂階段 (Employed Bees Phase)
            self._employed_bees_phase()
            
            # 2. 觀察蜂階段 (Onlooker Bees Phase)
            self._onlooker_bees_phase()
            
            # 3. 紀錄最佳解 (Memorize Best Solution)
            self._update_global_best()
            
            # 4. 偵查蜂階段 (Scout Bees Phase)
            self._scout_bees_phase()
            
            # 每訓練十次印出來一次
            if iteration % 10 == 0:
                print(f"Iter {iteration}: Best Makespan = {self.global_best_fit}")

        return self.global_best_sol, self.global_best_fit

    def _employed_bees_phase(self):
        """雇工蜂：對每一個解進行鄰域搜尋"""
        for i in range(self.pop_size):
            self._neighborhood_search(i)

    def _onlooker_bees_phase(self):
        """觀察蜂：根據適應度機率選擇解進行搜尋 (輪盤法)"""
        
        # 計算被選擇的機率 (Probability Calculation)
        # 因為我們的目標是「最小化時間」，所以時間越短，機率要越大
        # 公式轉換： prob = (1 / makespan) / sum(1 / makespan)
        # 為了避免除以無限大 (無效解)，我們給予極小的機率
        
        inv_fitness = []
        for f in self.fitness_values:
            if f == float('inf') or f == 0:
                inv_fitness.append(0.0001) # 給予極低權重
            else:
                inv_fitness.append(1.0 / f)
        
        total_inv_fitness = sum(inv_fitness)
        if total_inv_fitness == 0:
             probabilities = [1.0 / self.pop_size] * self.pop_size
        else:
             probabilities = [v / total_inv_fitness for v in inv_fitness]

        # 觀察蜂根據機率選擇並開發
        # 為了保持族群大小一致，我們執行 pop_size 次選擇與嘗試
        for _ in range(self.pop_size):
            # 輪盤選擇 (Roulette Wheel Selection)
            selected_index = self._roulette_wheel_selection(probabilities)
            self._neighborhood_search(selected_index)

    def _scout_bees_phase(self):
        """偵查蜂：檢查是否有解已經「停滯」太久"""
        for i in range(self.pop_size):
            if self.trial_counters[i] > self.limit:
                # 這裡用的不是隨機，是合法
                new_sol = self._generate_topological_individual()
                new_fit = self.scheduler.calculate_makespan(new_sol)
                
                # 重置狀態
                self.population[i] = new_sol
                self.fitness_values[i] = new_fit
                self.trial_counters[i] = 0
                # print(f"Scout Bee: Reset index {i}")

    def _neighborhood_search(self, index):
        """核心搜尋邏輯：產生新解 -> 貪婪選擇"""
        current_sol = self.population[index]
        current_fit = self.fitness_values[index]

        # 產生鄰近解 (Mutation)
        new_sol = self._mutate(current_sol)
        new_fit = self.scheduler.calculate_makespan(new_sol)

        # 貪婪選擇 (Greedy Selection)
        # 如果新解比較好 (時間較短)，就接受；否則 trial + 1
        if new_fit < current_fit:
            self.population[index] = new_sol
            self.fitness_values[index] = new_fit
            self.trial_counters[index] = 0 # 進步了，計數器歸零
        else:
            self.trial_counters[index] += 1 # 沒進步，計數器加一

    def _mutate(self, solution):
        """
        離散問題的突變算子。
        隨機選擇 'Swap' 或 'Insert' 以增加多樣性。
        """
        new_sol = copy.deepcopy(solution)
        n = len(new_sol)
        if n < 2: return new_sol

        operator = random.random()
        idx1, idx2 = random.sample(range(n), 2)

        if operator < 0.5:
            # 策略 A: Swap (交換)
            new_sol[idx1], new_sol[idx2] = new_sol[idx2], new_sol[idx1]
        else:
            # 策略 B: Insert (插入)
            # 把 idx1 的元素拿出來，插到 idx2 的位置
            element = new_sol.pop(idx1)
            new_sol.insert(idx2, element)
            
        return new_sol

    def _roulette_wheel_selection(self, probabilities):
        """實作輪盤法選擇索引"""
        r = random.random()
        cumulative_prob = 0.0
        for i, p in enumerate(probabilities):
            cumulative_prob += p
            if r < cumulative_prob:
                return i
        return len(probabilities) - 1

    def _update_global_best(self):
        """檢查整個族群，更新歷史最佳解"""
        for i in range(self.pop_size):
            if self.fitness_values[i] < self.global_best_fit:
                self.global_best_fit = self.fitness_values[i]
                self.global_best_sol = copy.deepcopy(self.population[i])


    def _generate_topological_individual(self):
        """產生一個符合依賴關係與手臂狀態的隨機合法解"""
        import copy
        import random
        
        valid_seq = []
        remaining = copy.deepcopy(self.task_ids)
        # hand_full: True = 手滿，同時記錄是哪個 task PICK 了這隻手
        hand_full = {"Left_Arm": False, "Right_Arm": False}
        # hand_last_pick: 記錄每隻手最後一次 PICK 的 task_id，用於救援時比對
        hand_last_pick = {"Left_Arm": None, "Right_Arm": None}
        
        max_attempts = len(remaining) * 10
        attempts = 0

        while remaining:
            attempts += 1
            if attempts > max_attempts:
                remaining.sort(key=lambda t: len(self.scheduler.tasks[t].get('dependencies', [])))
                valid_seq.extend(remaining)
                break

            available = []

            # --- 階段 1：尋找依賴已滿足且手臂狀態合法的任務 ---
            for t in remaining:
                deps = self.scheduler.tasks[t].get('dependencies', [])
                if not all(d in valid_seq for d in deps):
                    continue  # 依賴未滿足，跳過

                action = self.scheduler.tasks[t].get('action_type', '')
                hand = self.scheduler.tasks[t].get('hand_used')

                # 佔用手的動作：需要手是空的
                if action in ['PICK', 'RETRIEVE_FROM_TRAY']:
                    if hand and hand_full.get(hand, False):
                        continue  # 手滿，跳過
                # 釋放手的動作：需要手是滿的
                elif action in ['PLACE', 'STORE_ON_TRAY']:
                    if hand and not hand_full.get(hand, False):
                        continue  # 手空，跳過

                available.append(t)

            # --- 階段 2：死鎖救援 (available 為空) ---
            if not available:
                rescue = []

                # ★ 關鍵修正：只找「手滿的那隻手 + 依賴已滿足」的 PLACE/STORE_ON_TRAY
                # 不能讓它去放下其他手或還沒 PICK 的東西
                for t in remaining:
                    deps = self.scheduler.tasks[t].get('dependencies', [])
                    if not all(d in valid_seq for d in deps):
                        continue  # 依賴未滿足，不能做

                    action = self.scheduler.tasks[t].get('action_type', '')
                    hand = self.scheduler.tasks[t].get('hand_used')

                    if action in ['PLACE', 'STORE_ON_TRAY']:
                        # 只救援「這隻手確實是滿的」的放下動作
                        if hand and hand_full.get(hand, False):
                            rescue.append(t)
                    elif hand is None:
                        # 不需要手的動作（WAIT 等）也可以插入
                        rescue.append(t)

                if rescue:
                    available = rescue
                else:
                    # 再退一步：只看依賴是否滿足，完全忽略手臂狀態
                    for t in remaining:
                        deps = self.scheduler.tasks[t].get('dependencies', [])
                        if all(d in valid_seq for d in deps):
                            available.append(t)

                if not available:
                    print(f"[WARN] 拓樸生成器發生嚴重死鎖！嘗試暴力回退。剩餘任務: {remaining}")
                    remaining.sort(key=lambda t: len(self.scheduler.tasks[t].get('dependencies', [])))
                    valid_seq.extend(remaining)
                    break

            # --- 階段 3：隨機選擇並更新手臂狀態 ---
            chosen = random.choice(available)
            valid_seq.append(chosen)
            remaining.remove(chosen)

            action = self.scheduler.tasks[chosen].get('action_type', '')
            hand = self.scheduler.tasks[chosen].get('hand_used')
            if hand in hand_full:
                if action in ['PICK', 'RETRIEVE_FROM_TRAY']:
                    hand_full[hand] = True
                    hand_last_pick[hand] = chosen  # 記錄這隻手拿了什麼
                elif action in ['PLACE', 'STORE_ON_TRAY']:
                    hand_full[hand] = False
                    hand_last_pick[hand] = None    # 手放空了，清除記錄

        return valid_seq
    # def _generate_topological_individual(self):
    #     """產生一個絕對符合依賴關係的隨機初始解"""
    #     import copy
    #     import random
        
    #     valid_seq = []
    #     remaining = copy.deepcopy(self.task_ids)
        
    #     hand_full = {"Left_Arm": False, "Right_Arm": False}

    #     while remaining:
    #         # 找出所有「依賴條件已經被滿足」的任務
    #         available = []
    #         for t in remaining:
    #             deps = self.scheduler.tasks[t].get('dependencies', [])
    #             # 檢查這個任務的所有依賴，是不是都已經在 valid_seq 裡面了
    #             if all(d in valid_seq for d in deps):
    #                 action = self.scheduler.tasks[t].get('action_type', '')
    #                 hand = self.scheduler.tasks[t].get('hand_used')
    #                 # 拿取身上的托盤也是拿取
    #                 occupy_actions = ['PICK', 'RETRIEVE_FROM_TRAY']
    #                 if action in occupy_actions and hand and hand_full.get(hand, False):
    #                     continue

    #             available.append(t)
    #         # 萬一遇到死鎖 (理論上不會，除非 LLM 給了互相依賴的無效資料)，退回純隨機避免無窮迴圈
    #         if not available:
    #             random.shuffle(remaining)
    #             valid_seq.extend(remaining)
    #             break
                
    #         # 從可執行的任務中，隨機挑選一個加入序列，確保多樣性
    #         chosen = random.choice(available)
    #         valid_seq.append(chosen)
    #         remaining.remove(chosen)
            

    #         action = self.scheduler.tasks[chosen].get('action_type', '')
    #         hand = self.scheduler.tasks[chosen].get('hand_used')
    #         if hand in hand_full:
    #             if action in ['PICK', 'RETRIEVE_FROM_TRAY']:
    #                 hand_full[hand] = True
    #             elif action in ['PLACE', 'STORE_ON_TRAY']: 
    #                 hand_full[hand] = False

    #     return valid_seq