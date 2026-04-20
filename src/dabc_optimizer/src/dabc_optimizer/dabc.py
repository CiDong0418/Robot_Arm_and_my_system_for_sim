import random
import copy
import math
import time
from collections import defaultdict
from collections import deque
from .fitness import TaskScheduler


FREE_HAND_REQUIRED_ACTIONS = {"WATER_DISPENSER", "OPEN_CABINET", "CLOSE_CABINET"}

class DABC:
    def __init__(
        self,
        task_lookup,
        population_size=20,
        max_iterations=100,
        limit=20,
        initial_seq=None,
        w1=1.0,
        w2=1.0,
        w3=1.0,
        w4=1.0,
        neighbor_attempts_per_bee=1,
        onlooker_multiplier=1.0,
        dynamic_breadth_enabled=True,
        max_neighbor_attempts_per_bee=5,
        max_onlooker_multiplier=3.0,
        dynamic_onlooker_step=0.25,
        dynamic_stagnation_window_blocks=2,
        dynamic_improve_threshold_pct=0.3,
        dynamic_high_infeasible_threshold=0.78,
        dynamic_recovery_improve_pct=1.0,
        dynamic_recovery_infeasible_threshold=0.60,
    ):
        
        self.task_ids = list(task_lookup.keys())
        self.scheduler = TaskScheduler(task_lookup, w1=w1, w2=w2, w3=w3, w4=w4)
        self.pop_size = population_size  # 族群大小
        self.max_iter = max_iterations 
        self.limit = limit  # 偵查蜂重複次數限制 如果一個解連續 limit 次沒變好，就放棄它
        self.neighbor_attempts_per_bee = max(1, int(neighbor_attempts_per_bee))
        self.onlooker_multiplier = max(1.0, float(onlooker_multiplier))
        self.base_neighbor_attempts_per_bee = int(self.neighbor_attempts_per_bee)
        self.base_onlooker_multiplier = float(self.onlooker_multiplier)
        self.dynamic_breadth_enabled = bool(dynamic_breadth_enabled)
        self.max_neighbor_attempts_per_bee = max(self.base_neighbor_attempts_per_bee, int(max_neighbor_attempts_per_bee))
        self.max_onlooker_multiplier = max(self.base_onlooker_multiplier, float(max_onlooker_multiplier))
        self.dynamic_onlooker_step = max(0.05, float(dynamic_onlooker_step))
        self.dynamic_stagnation_window_blocks = max(1, int(dynamic_stagnation_window_blocks))
        self.dynamic_improve_threshold_pct = max(0.0, float(dynamic_improve_threshold_pct))
        self.dynamic_high_infeasible_threshold = min(1.0, max(0.0, float(dynamic_high_infeasible_threshold)))
        self.dynamic_recovery_improve_pct = max(0.0, float(dynamic_recovery_improve_pct))
        self.dynamic_recovery_infeasible_threshold = min(1.0, max(0.0, float(dynamic_recovery_infeasible_threshold)))
        self._prev_block_best_fit = float('inf')
        self._stagnation_blocks = 0
        self._recovery_blocks = 0
        
        
        self.population = [] # 存解
        self.fitness_values = [] # 存適應值
        self.trial_counters = [] # 存 沒有 進步次數
        self._last_mutation_operator = None
        self.max_repair_attempts = 6
        self.current_iteration = 0
        self._current_phase = "phase1_feasibility"
        self.phase1_min_iters = max(10, int(self.max_iter * 0.15))
        self.phase1_max_iters = max(self.phase1_min_iters, int(self.max_iter * 0.45))
        self.phase1_exit_threshold = 0.2
        self._recent_candidate_infeasible = deque(maxlen=300)
        self._operator_names = ["swap", "insert", "segment_shuffle", "parent_segment_exchange"]
        self._operator_weights = {
            "swap": 0.32,
            "insert": 0.32,
            "segment_shuffle": 0.2,
            "parent_segment_exchange": 0.16,
        }
        self._operator_recent = {op: deque(maxlen=200) for op in self._operator_names}
        self.elite_archive_size = max(3, min(8, self.pop_size // 3))
        self.elite_archive = []
        self._init_diagnostics()

        for i in range(self.pop_size):
            if i == 0 and initial_seq is not None:
                # 如果有提供初始解，第一個解就用它
                individual = copy.deepcopy(initial_seq)
                llm_fit = self.scheduler.calculate_fitness(individual)
                print(f"==========================================")
                print(f"🐝 [Baseline] 第 1 隻蜜蜂 (LLM 全域排程) 初始 Fitness: {llm_fit}")
                print(f"==========================================")

            # individual = copy.deepcopy(self.task_ids)
            # random.shuffle(individual)
            # self.population.append(individual)
            else:
                # 剩下的 9 隻蜜蜂
                individual = self._generate_topological_individual()
            
            self.population.append(individual)
            # 計算適應值
            fit = self.scheduler.calculate_fitness(individual)
            self.fitness_values.append(fit)   # 存放適應值
            self.trial_counters.append(0) # 初始化計數器為 0 紀錄每一個解沒有進步的次數


        # 紀錄全域最佳解
        self.global_best_sol = None
        self.global_best_fit = float('inf')
        self._update_global_best()
        self._update_elite_archive_from_population()

    def optimize(self):
        """執行完整版 DABC 迭代"""
        self._reset_iteration_diagnostics()
        start_time = time.perf_counter()
        last_log_time = start_time
        
        for iteration in range(self.max_iter):
            self.current_iteration = iteration
            self._current_phase = self._determine_phase(iteration)

            # 1. 雇工蜂階段 (Employed Bees Phase)
            self._employed_bees_phase()
            
            # 2. 觀察蜂階段 (Onlooker Bees Phase)
            self._onlooker_bees_phase()
            
            # 3. 紀錄最佳解 (Memorize Best Solution)
            self._update_global_best()
            
            # 4. 偵查蜂階段 (Scout Bees Phase)
            self._scout_bees_phase()

            # 5. 週期性重新注入多樣解，降低困在局部最佳的風險
            if (iteration + 1) % 20 == 0:
                self._diversify_population(replace_ratio=0.3)
                self._update_elite_archive_from_population()

            if (iteration + 1) % 10 == 0:
                self._adapt_operator_weights()
            
            # 每訓練十次印出來一次
            if (iteration + 1) % 10 == 0:
                now = time.perf_counter()
                block_elapsed = now - last_log_time
                total_elapsed = now - start_time
                last_log_time = now
                improve_pct_10iter = self._compute_improve_pct_10iter(self._prev_block_best_fit, self.global_best_fit)
                self._prev_block_best_fit = self.global_best_fit
                self._diag["iter_time_logs"].append({
                    "iteration": iteration + 1,
                    "elapsed_10_iters_sec": block_elapsed,
                    "elapsed_total_sec": total_elapsed,
                    "phase": self._current_phase,
                    "improve_pct_10iter": improve_pct_10iter,
                    "neighbor_attempts_per_bee": int(self.neighbor_attempts_per_bee),
                    "onlooker_multiplier": float(self.onlooker_multiplier),
                })
                recent_infeasible_rate = self._recent_infeasible_rate()
                self._auto_tune_search_breadth(
                    iteration=iteration + 1,
                    improve_pct_10iter=improve_pct_10iter,
                    recent_infeasible_rate=recent_infeasible_rate,
                )
                print(
                    f"Iter {iteration + 1}: Best Fitness = {self.global_best_fit} | "
                    f"accepted={self._diag['accepted']} "
                    f"rejected_infeasible={self._diag['rejected_infeasible']} "
                    f"rejected_not_better={self._diag['rejected_not_better']} "
                    f"phase={self._current_phase} "
                    f"infeasible_rate_recent={recent_infeasible_rate:.3f} "
                    f"improve_pct_10iter={improve_pct_10iter:.3f}% "
                    f"neighbor_attempts_per_bee={self.neighbor_attempts_per_bee} "
                    f"onlooker_multiplier={self.onlooker_multiplier:.2f} "
                    f"time_10iter={block_elapsed:.3f}s "
                    f"time_total={total_elapsed:.3f}s"
                )

        return self.global_best_sol, self.global_best_fit

    def _init_diagnostics(self):
        self._diag = {
            "neighbor_calls": 0,
            "accepted": 0,
            "rejected_infeasible": 0,
            "rejected_not_better": 0,
            "prefilter_rejected": 0,
            "operator_stats": defaultdict(lambda: {"attempts": 0, "accepted": 0, "rejected_infeasible": 0, "rejected_not_better": 0}),
            "repair_retry_success": 0,
            "repair_retry_fail": 0,
            "iter_time_logs": [],
            "breadth_adjustments": [],
        }

    def _reset_iteration_diagnostics(self):
        self._init_diagnostics()

    def _parent_of_task(self, task_id):
        task = self.scheduler.tasks.get(task_id, {})
        parent = task.get("parent_id")
        if parent is not None:
            return str(parent)
        text = str(task_id)
        if "_" in text:
            return text.split("_", 1)[0]
        return None

    def _compute_parent_interleaving_ratio(self, sequence):
        if not sequence or len(sequence) < 2:
            return 0.0
        switches = 0
        comparable_pairs = 0
        for idx in range(1, len(sequence)):
            p_prev = self._parent_of_task(sequence[idx - 1])
            p_cur = self._parent_of_task(sequence[idx])
            if p_prev is None or p_cur is None:
                continue
            comparable_pairs += 1
            if p_prev != p_cur:
                switches += 1
        if comparable_pairs == 0:
            return 0.0
        return float(switches) / float(comparable_pairs)

    def get_diagnostics(self):
        op_stats = {}
        for op, data in self._diag["operator_stats"].items():
            op_stats[op] = dict(data)
        best_interleave = self._compute_parent_interleaving_ratio(self.global_best_sol or [])
        return {
            "neighbor_calls": int(self._diag["neighbor_calls"]),
            "accepted": int(self._diag["accepted"]),
            "rejected_infeasible": int(self._diag["rejected_infeasible"]),
            "rejected_not_better": int(self._diag["rejected_not_better"]),
            "prefilter_rejected": int(self._diag["prefilter_rejected"]),
            "best_parent_interleaving_ratio": best_interleave,
            "repair_retry_success": int(self._diag["repair_retry_success"]),
            "repair_retry_fail": int(self._diag["repair_retry_fail"]),
            "phase": self._current_phase,
            "neighbor_attempts_per_bee": int(self.neighbor_attempts_per_bee),
            "onlooker_multiplier": float(self.onlooker_multiplier),
            "dynamic_breadth_enabled": bool(self.dynamic_breadth_enabled),
            "dynamic_breadth_config": {
                "max_neighbor_attempts_per_bee": int(self.max_neighbor_attempts_per_bee),
                "max_onlooker_multiplier": float(self.max_onlooker_multiplier),
                "dynamic_onlooker_step": float(self.dynamic_onlooker_step),
                "dynamic_stagnation_window_blocks": int(self.dynamic_stagnation_window_blocks),
                "dynamic_improve_threshold_pct": float(self.dynamic_improve_threshold_pct),
                "dynamic_high_infeasible_threshold": float(self.dynamic_high_infeasible_threshold),
                "dynamic_recovery_improve_pct": float(self.dynamic_recovery_improve_pct),
                "dynamic_recovery_infeasible_threshold": float(self.dynamic_recovery_infeasible_threshold),
            },
            "dynamic_breadth_state": {
                "stagnation_blocks": int(self._stagnation_blocks),
                "recovery_blocks": int(self._recovery_blocks),
            },
            "operator_weights": dict(self._operator_weights),
            "elite_archive_size": len(self.elite_archive),
            "iter_time_logs": list(self._diag["iter_time_logs"]),
            "breadth_adjustments": list(self._diag["breadth_adjustments"]),
            "operator_stats": op_stats,
        }

    @staticmethod
    def _compute_improve_pct_10iter(prev_best, current_best):
        if prev_best == float('inf') and current_best == float('inf'):
            return 0.0
        if prev_best == float('inf') and current_best != float('inf'):
            return 100.0
        if current_best == float('inf'):
            return 0.0

        denom = max(1e-9, abs(float(prev_best)))
        delta = float(prev_best) - float(current_best)
        return max(0.0, (delta / denom) * 100.0)

    def _auto_tune_search_breadth(self, iteration, improve_pct_10iter, recent_infeasible_rate):
        if not self.dynamic_breadth_enabled:
            return

        stagnating = improve_pct_10iter < self.dynamic_improve_threshold_pct
        infeasible_high = recent_infeasible_rate >= self.dynamic_high_infeasible_threshold

        if stagnating or infeasible_high:
            self._stagnation_blocks += 1
            self._recovery_blocks = 0
        else:
            self._stagnation_blocks = max(0, self._stagnation_blocks - 1)
            recovering = (
                improve_pct_10iter >= self.dynamic_recovery_improve_pct
                and recent_infeasible_rate <= self.dynamic_recovery_infeasible_threshold
            )
            if recovering:
                self._recovery_blocks += 1
            else:
                self._recovery_blocks = 0

        if self._stagnation_blocks >= self.dynamic_stagnation_window_blocks:
            old_neighbor = self.neighbor_attempts_per_bee
            old_onlooker = self.onlooker_multiplier

            self.neighbor_attempts_per_bee = min(
                self.max_neighbor_attempts_per_bee,
                self.neighbor_attempts_per_bee + 1,
            )
            self.onlooker_multiplier = min(
                self.max_onlooker_multiplier,
                self.onlooker_multiplier + self.dynamic_onlooker_step,
            )

            if (
                self.neighbor_attempts_per_bee != old_neighbor
                or abs(self.onlooker_multiplier - old_onlooker) > 1e-9
            ):
                self._diag["breadth_adjustments"].append({
                    "iteration": int(iteration),
                    "action": "expand",
                    "reason": "stagnation_or_high_infeasible",
                    "improve_pct_10iter": float(improve_pct_10iter),
                    "infeasible_rate_recent": float(recent_infeasible_rate),
                    "neighbor_attempts_per_bee_before": int(old_neighbor),
                    "neighbor_attempts_per_bee_after": int(self.neighbor_attempts_per_bee),
                    "onlooker_multiplier_before": float(old_onlooker),
                    "onlooker_multiplier_after": float(self.onlooker_multiplier),
                })
            self._stagnation_blocks = 0

        if self._recovery_blocks >= 2:
            old_neighbor = self.neighbor_attempts_per_bee
            old_onlooker = self.onlooker_multiplier

            self.neighbor_attempts_per_bee = max(
                self.base_neighbor_attempts_per_bee,
                self.neighbor_attempts_per_bee - 1,
            )
            self.onlooker_multiplier = max(
                self.base_onlooker_multiplier,
                self.onlooker_multiplier - self.dynamic_onlooker_step,
            )

            if (
                self.neighbor_attempts_per_bee != old_neighbor
                or abs(self.onlooker_multiplier - old_onlooker) > 1e-9
            ):
                self._diag["breadth_adjustments"].append({
                    "iteration": int(iteration),
                    "action": "contract",
                    "reason": "recovery",
                    "improve_pct_10iter": float(improve_pct_10iter),
                    "infeasible_rate_recent": float(recent_infeasible_rate),
                    "neighbor_attempts_per_bee_before": int(old_neighbor),
                    "neighbor_attempts_per_bee_after": int(self.neighbor_attempts_per_bee),
                    "onlooker_multiplier_before": float(old_onlooker),
                    "onlooker_multiplier_after": float(self.onlooker_multiplier),
                })
            self._recovery_blocks = 0

    def _determine_phase(self, iteration):
        if iteration < self.phase1_min_iters:
            return "phase1_feasibility"
        if iteration < self.phase1_max_iters and self._recent_infeasible_rate() > self.phase1_exit_threshold:
            return "phase1_feasibility"
        return "phase2_makespan"

    def _recent_infeasible_rate(self):
        if not self._recent_candidate_infeasible:
            return 1.0
        return float(sum(self._recent_candidate_infeasible)) / float(len(self._recent_candidate_infeasible))

    def _objective_key(self, fit, violation_score):
        if self._current_phase == "phase1_feasibility":
            if fit == float('inf'):
                return (1, int(violation_score))
            return (0, float(fit))

        if fit == float('inf'):
            return (1, float('inf'))
        return (0, float(fit))

    def _compute_parent_signature(self, sequence, max_tokens=16):
        compact = []
        last = None
        for tid in sequence:
            parent = self._parent_of_task(tid)
            if parent is None:
                continue
            if parent != last:
                compact.append(parent)
                last = parent
            if len(compact) >= max_tokens:
                break
        return "|".join(compact)

    def _upsert_elite(self, sol, fit):
        if fit == float('inf'):
            return
        signature = self._compute_parent_signature(sol)
        if not signature:
            return
        for i, entry in enumerate(self.elite_archive):
            if entry["signature"] == signature:
                if fit < entry["fit"]:
                    self.elite_archive[i] = {
                        "sol": copy.deepcopy(sol),
                        "fit": fit,
                        "signature": signature,
                    }
                return

        self.elite_archive.append({
            "sol": copy.deepcopy(sol),
            "fit": fit,
            "signature": signature,
        })
        self.elite_archive.sort(key=lambda x: x["fit"])

        if len(self.elite_archive) > self.elite_archive_size:
            self.elite_archive = self.elite_archive[:self.elite_archive_size]

    def _update_elite_archive_from_population(self):
        ranked = sorted(range(self.pop_size), key=lambda i: self.fitness_values[i])
        for idx in ranked:
            fit = self.fitness_values[idx]
            if fit == float('inf'):
                continue
            self._upsert_elite(self.population[idx], fit)

    def _adapt_operator_weights(self):
        raw_scores = {}
        for op in self._operator_names:
            recent = self._operator_recent.get(op, deque())
            attempts = len(recent)
            accepted = sum(1 for x in recent if x)
            ratio = (accepted + 1.0) / (attempts + 2.0)
            # 給 parent-aware 算子一點探索偏好，避免早期被完全壓掉
            if op == "parent_segment_exchange":
                ratio *= 1.1
            raw_scores[op] = ratio

        total = sum(raw_scores.values()) or 1.0
        floor = 0.08
        adjusted = {}
        for op in self._operator_names:
            adjusted[op] = max(floor, raw_scores[op] / total)

        adjusted_total = sum(adjusted.values()) or 1.0
        for op in self._operator_names:
            self._operator_weights[op] = adjusted[op] / adjusted_total

    def _employed_bees_phase(self):
        """雇工蜂：對每一個解進行鄰域搜尋"""
        for i in range(self.pop_size):
            for _ in range(self.neighbor_attempts_per_bee):
                self._neighborhood_search(i)

    def _onlooker_bees_phase(self):
        """觀察蜂：根據適應度機率選擇解進行搜尋 (輪盤法)"""
        
        # 計算被選擇的機率 (Probability Calculation)
        # 因為我們的目標是「最小化 fitness」，所以 fitness 越低，機率要越大
        # 公式轉換： prob = (1 / fitness) / sum(1 / fitness)
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
        # 透過 multiplier 放大每代探索寬度，而不是只拉長代數。
        onlooker_budget = max(self.pop_size, int(round(self.pop_size * self.onlooker_multiplier)))
        for _ in range(onlooker_budget):
            # 輪盤選擇 (Roulette Wheel Selection)
            selected_index = self._roulette_wheel_selection(probabilities)
            self._neighborhood_search(selected_index)

    def _scout_bees_phase(self):
        """偵查蜂：檢查是否有解已經「停滯」太久"""
        for i in range(self.pop_size):
            if self.trial_counters[i] > self.limit:
                # 這裡用的不是隨機，是合法
                new_sol = self._generate_topological_individual()
                new_fit = self.scheduler.calculate_fitness(new_sol)
                
                # 重置狀態
                self.population[i] = new_sol
                self.fitness_values[i] = new_fit
                self.trial_counters[i] = 0
                # print(f"Scout Bee: Reset index {i}")

    def _evaluate_with_repair_retry(self, candidate):
        """Evaluate candidate and retry repair several times if infeasible."""
        candidate_fit = self.scheduler.calculate_fitness(candidate)
        if candidate_fit != float('inf'):
            return candidate, candidate_fit

        # Retry with repaired variants to raise feasible-neighbor density.
        for _ in range(self.max_repair_attempts):
            re_repaired = self._repair_topological_order(candidate)
            re_fit = self.scheduler.calculate_fitness(re_repaired)
            if re_fit != float('inf'):
                self._diag["repair_retry_success"] += 1
                return re_repaired, re_fit

        self._diag["repair_retry_fail"] += 1
        return candidate, candidate_fit

    def _neighborhood_search(self, index):
        """核心搜尋邏輯：產生新解 -> 貪婪選擇"""
        current_sol = self.population[index]
        current_fit = self.fitness_values[index]
        self._diag["neighbor_calls"] += 1

        # 產生鄰近解 (Mutation)
        new_sol = self._mutate(current_sol)
        operator = self._last_mutation_operator or "unknown"
        self._diag["operator_stats"][operator]["attempts"] += 1

        pre_ok, pre_violation = self._quick_feasibility_check(new_sol)
        if not pre_ok:
            # feasible-first: 不通過快速依賴/手臂檢查就先修一次，不直接進昂貴評分
            repaired = self._repair_topological_order(new_sol)
            repaired_ok, repaired_violation = self._quick_feasibility_check(repaired)
            if repaired_ok:
                new_sol, new_fit = self._evaluate_with_repair_retry(repaired)
                pre_violation = repaired_violation
            else:
                new_sol = repaired
                new_fit = float('inf')
                pre_violation = repaired_violation
                self._diag["prefilter_rejected"] += 1
        else:
            new_sol, new_fit = self._evaluate_with_repair_retry(new_sol)

        self._recent_candidate_infeasible.append(1 if new_fit == float('inf') else 0)

        current_ok, current_violation = self._quick_feasibility_check(current_sol)
        if current_fit != float('inf'):
            current_violation = 0
        elif current_ok:
            current_violation = 1

        current_key = self._objective_key(current_fit, current_violation)
        new_key = self._objective_key(new_fit, pre_violation)

        # 貪婪選擇 (Greedy Selection)
        # 如果新解比較好 (fitness 較低)，就接受；否則 trial + 1
        if new_key < current_key:
            self.population[index] = new_sol
            self.fitness_values[index] = new_fit
            self.trial_counters[index] = 0 # 進步了，計數器歸零
            self._diag["accepted"] += 1
            self._diag["operator_stats"][operator]["accepted"] += 1
            self._operator_recent.setdefault(operator, deque(maxlen=200)).append(True)
        else:
            self.trial_counters[index] += 1 # 沒進步，計數器加一
            if new_fit == float('inf'):
                self._diag["rejected_infeasible"] += 1
                self._diag["operator_stats"][operator]["rejected_infeasible"] += 1
            else:
                self._diag["rejected_not_better"] += 1
                self._diag["operator_stats"][operator]["rejected_not_better"] += 1
            self._operator_recent.setdefault(operator, deque(maxlen=200)).append(False)

    def _mutate(self, solution):
        """
        離散問題的突變算子。
        隨機選擇 'Swap' 或 'Insert' 以增加多樣性。
        """
        new_sol = copy.deepcopy(solution)
        n = len(new_sol)
        if n < 2: return new_sol

        idx1, idx2 = random.sample(range(n), 2)
        operator = random.choices(self._operator_names, weights=[self._operator_weights[o] for o in self._operator_names], k=1)[0]

        if operator == "swap":
            # 策略 A: Swap (交換)
            self._last_mutation_operator = "swap"
            new_sol[idx1], new_sol[idx2] = new_sol[idx2], new_sol[idx1]
        elif operator == "insert":
            # 策略 B: Insert (插入)
            self._last_mutation_operator = "insert"
            element = new_sol.pop(idx1)
            new_sol.insert(idx2, element)
        elif operator == "segment_shuffle":
            # 策略 C: 區段打亂
            self._last_mutation_operator = "segment_shuffle"
            l, r = sorted([idx1, idx2])
            segment = new_sol[l:r + 1]
            random.shuffle(segment)
            new_sol[l:r + 1] = segment
        else:
            self._last_mutation_operator = "parent_segment_exchange"
            exchanged = self._parent_segment_exchange(new_sol)
            if exchanged is not None:
                new_sol = exchanged
            else:
                # parent-aware 不可用時回退到 swap，避免浪費一次鄰域搜尋
                self._last_mutation_operator = "swap"
                new_sol[idx1], new_sol[idx2] = new_sol[idx2], new_sol[idx1]

        # 重要：把突變結果修復成「依賴+手臂狀態可行」序列，提升可行解密度
        return self._repair_topological_order(new_sol)

    def _parent_segment_exchange(self, sequence):
        if len(sequence) < 4:
            return None

        runs = []
        start = 0
        while start < len(sequence):
            parent = self._parent_of_task(sequence[start])
            end = start + 1
            while end < len(sequence) and self._parent_of_task(sequence[end]) == parent:
                end += 1
            if parent is not None and end > start:
                runs.append((start, end, parent))
            start = end

        if len(runs) < 2:
            return None

        for _ in range(12):
            run_a = random.choice(runs)
            choices_b = [r for r in runs if r[2] != run_a[2] and not (r[0] < run_a[1] and run_a[0] < r[1])]
            if not choices_b:
                continue
            run_b = random.choice(choices_b)

            a_start, a_end, _ = run_a
            b_start, b_end, _ = run_b
            if a_start == b_start and a_end == b_end:
                continue

            if a_start < b_start:
                seg_a = sequence[a_start:a_end]
                seg_b = sequence[b_start:b_end]
                return sequence[:a_start] + seg_b + sequence[a_end:b_start] + seg_a + sequence[b_end:]

            seg_b = sequence[b_start:b_end]
            seg_a = sequence[a_start:a_end]
            return sequence[:b_start] + seg_a + sequence[b_end:a_start] + seg_b + sequence[a_end:]

        return None

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
            self._upsert_elite(self.population[i], self.fitness_values[i])

    def _diversify_population(self, replace_ratio=0.3):
        replace_count = max(1, int(self.pop_size * float(replace_ratio)))
        ranked = sorted(range(self.pop_size), key=lambda i: self.fitness_values[i], reverse=True)
        for idx in ranked[:replace_count]:
            if self.elite_archive and random.random() < 0.6:
                seed = copy.deepcopy(random.choice(self.elite_archive)["sol"])
                new_sol = self._mutate(seed)
            else:
                new_sol = self._generate_topological_individual()
            self.population[idx] = new_sol
            self.fitness_values[idx] = self.scheduler.calculate_fitness(new_sol)
            self.trial_counters[idx] = 0
            self._upsert_elite(self.population[idx], self.fitness_values[idx])

    def _quick_feasibility_check(self, sequence):
        built = set()
        hand_full = {'Left_Arm': False, 'Right_Arm': False, '_held_count': 0}
        violations = 0

        for tid in sequence:
            task = self.scheduler.tasks.get(tid)
            if task is None:
                violations += 1
                continue

            deps = task.get('dependencies', [])
            if any(dep not in built for dep in deps):
                violations += 1
                continue

            action = str(task.get('action_type', '')).upper()
            hand = task.get('hand_used')

            if action in ['PICK', 'RETRIEVE_FROM_TRAY']:
                if hand in hand_full and hand_full.get(hand, False):
                    violations += 1
                    continue
                if hand is None and hand_full.get('_held_count', 0) >= 2:
                    violations += 1
                    continue
                if hand in hand_full:
                    hand_full[hand] = True
                if hand_full.get('_held_count', 0) < 2:
                    hand_full['_held_count'] += 1

            elif action in ['PLACE', 'STORE_ON_TRAY']:
                if hand in hand_full and not hand_full.get(hand, False):
                    violations += 1
                    continue
                if hand is None and hand_full.get('_held_count', 0) <= 0:
                    violations += 1
                    continue
                if hand in hand_full:
                    hand_full[hand] = False
                if hand_full.get('_held_count', 0) > 0:
                    hand_full['_held_count'] -= 1

            elif action in FREE_HAND_REQUIRED_ACTIONS:
                if hand_full.get('_held_count', 0) >= 2:
                    violations += 1
                    continue

            built.add(tid)

        return violations == 0, violations

    def _is_dependency_satisfied(self, task_id, built_seq):
        deps = self.scheduler.tasks[task_id].get('dependencies', [])
        return all(d in built_seq for d in deps)

    def _is_hand_state_valid_for_append(self, task_id, hand_full):
        action = str(self.scheduler.tasks[task_id].get('action_type', '')).upper()
        hand = self.scheduler.tasks[task_id].get('hand_used')
        held_count = int(hand_full.get('_held_count', 0))

        if action in ['PICK', 'RETRIEVE_FROM_TRAY']:
            if hand and hand_full.get(hand, False):
                return False
            if hand is None and held_count >= 2:
                return False

        elif action in ['PLACE', 'STORE_ON_TRAY']:
            if hand and not hand_full.get(hand, False):
                return False
            if hand is None and held_count <= 0:
                return False

        elif action in FREE_HAND_REQUIRED_ACTIONS:
            if held_count >= 2:
                return False

        return True

    def _repair_topological_order(self, priority_order):
        priority_rank = {tid: i for i, tid in enumerate(priority_order)}
        remaining = [tid for tid in self.task_ids if tid in priority_rank]
        missing = [tid for tid in self.task_ids if tid not in priority_rank]
        remaining.extend(missing)

        built_seq = []
        hand_full = {'Left_Arm': False, 'Right_Arm': False, '_held_count': 0}

        while remaining:
            available = []
            for tid in remaining:
                if not self._is_dependency_satisfied(tid, built_seq):
                    continue
                if not self._is_hand_state_valid_for_append(tid, hand_full):
                    continue
                available.append(tid)

            if not available:
                # 救援：允許先做可釋放手臂的動作
                rescue = []
                for tid in remaining:
                    if not self._is_dependency_satisfied(tid, built_seq):
                        continue
                    action = str(self.scheduler.tasks[tid].get('action_type', '')).upper()
                    hand = self.scheduler.tasks[tid].get('hand_used')
                    if action in ['PLACE', 'STORE_ON_TRAY'] and hand and hand_full.get(hand, False):
                        rescue.append(tid)

                available = rescue

            if not available:
                # 最後保底：僅依賴合法即可，避免無窮迴圈
                for tid in remaining:
                    if self._is_dependency_satisfied(tid, built_seq):
                        available.append(tid)

            if not available:
                # 無法修復時保留剩餘順序直接接上
                built_seq.extend(remaining)
                break

            # 以優先序前 3 名隨機選一個，兼顧修復與探索
            available.sort(key=lambda tid: priority_rank.get(tid, len(priority_rank)))
            k = min(3, len(available))
            chosen = random.choice(available[:k])

            built_seq.append(chosen)
            remaining.remove(chosen)

            action = str(self.scheduler.tasks[chosen].get('action_type', '')).upper()
            hand = self.scheduler.tasks[chosen].get('hand_used')
            if hand in hand_full:
                was_full = bool(hand_full[hand])
                if action in ['PICK', 'RETRIEVE_FROM_TRAY']:
                    hand_full[hand] = True
                    if not was_full:
                        hand_full['_held_count'] += 1
                elif action in ['PLACE', 'STORE_ON_TRAY']:
                    hand_full[hand] = False
                    if was_full and hand_full['_held_count'] > 0:
                        hand_full['_held_count'] -= 1
            elif hand is None:
                if action in ['PICK', 'RETRIEVE_FROM_TRAY'] and hand_full['_held_count'] < 2:
                    hand_full['_held_count'] += 1
                elif action in ['PLACE', 'STORE_ON_TRAY'] and hand_full['_held_count'] > 0:
                    hand_full['_held_count'] -= 1

        return built_seq


    def _generate_topological_individual(self):
        """產生一個符合依賴關係與手臂狀態的隨機合法解"""
        import copy
        import random
        
        valid_seq = []
        remaining = copy.deepcopy(self.task_ids)
        # hand_full: True = 手滿，同時記錄是哪個 task PICK 了這隻手
        hand_full = {"Left_Arm": False, "Right_Arm": False, "_held_count": 0}
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
                    if hand is None and hand_full.get('_held_count', 0) >= 2:
                        continue  # 未指定手但雙手都滿，跳過
                # 釋放手的動作：需要手是滿的
                elif action in ['PLACE', 'STORE_ON_TRAY']:
                    if hand and not hand_full.get(hand, False):
                        continue  # 手空，跳過
                    if hand is None and hand_full.get('_held_count', 0) <= 0:
                        continue  # 未指定手但目前無持物，跳過
                # 指定動作需要至少有一隻手是空的
                elif action in FREE_HAND_REQUIRED_ACTIONS:
                    if hand_full.get('_held_count', 0) >= 2:
                        continue

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
                was_full = bool(hand_full[hand])
                if action in ['PICK', 'RETRIEVE_FROM_TRAY']:
                    hand_full[hand] = True
                    if not was_full:
                        hand_full['_held_count'] += 1
                    hand_last_pick[hand] = chosen  # 記錄這隻手拿了什麼
                elif action in ['PLACE', 'STORE_ON_TRAY']:
                    hand_full[hand] = False
                    if was_full and hand_full['_held_count'] > 0:
                        hand_full['_held_count'] -= 1
                    hand_last_pick[hand] = None    # 手放空了，清除記錄
            elif hand is None:
                if action in ['PICK', 'RETRIEVE_FROM_TRAY'] and hand_full['_held_count'] < 2:
                    hand_full['_held_count'] += 1
                elif action in ['PLACE', 'STORE_ON_TRAY'] and hand_full['_held_count'] > 0:
                    hand_full['_held_count'] -= 1

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