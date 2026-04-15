# Eval Task File Format (Simple)

File: `src/task_manager/data/eval_tasks.json`

Use this file as a pure text prompt bank.
At runtime, randomly pick any `id`, then send the corresponding `text` to your planner.

## Top-level structure
- `schema_version`
- `dataset_name`
- `usage`
- `beginner` / `intermediate` / `advanced`

Each level is a list of tasks. Each task only needs:
- `id`
- `text`

## Example
```json
{
  "id": "B004",
  "text": "把餐桌上的香蕉移到吧台。"
}
```

## ID suggestion
- Beginner: `B001`-`B030`
- Intermediate: `I001`-`I035`
- Advanced: `A001`-`A035`
