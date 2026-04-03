# C++ Flat API → Pythonic Facade: Prompt Chain

This skill uses a **sequential prompt chain** instead of a single prompt.
Do NOT paste this file into the AI. Use the individual prompts below in order.

## Prompt Sequence

| Step | File | What the AI does |
|------|------|-----------------|
| 1 | [prompts/01-parse-header.md](prompts/01-parse-header.md) | Parse C++ header → function_table.json |
| 2 | [prompts/02-gen-bindings.md](prompts/02-gen-bindings.md) | Generate pybind11 binding code |
| 3 | [prompts/03-build-registry.md](prompts/03-build-registry.md) | Build type dispatch registry |
| 4 | [prompts/04-write-facade.md](prompts/04-write-facade.md) | Write Pythonic facade |
| 5 | [prompts/05-add-preprocessor.md](prompts/05-add-preprocessor.md) | Add pluggable preprocessing |
| 6 | [prompts/06-torch-frontend.md](prompts/06-torch-frontend.md) | Write torch.Tensor API |
| 7 | [prompts/07-build-system.md](prompts/07-build-system.md) | Set up build system |
| 8 | [prompts/08-test-verify.md](prompts/08-test-verify.md) | Write tests |

## How to Use

1. Start with Step 1. Give the AI the prompt + your C++ header file.
2. Check the AI's output. If good, proceed to Step 2.
3. Give the AI the next prompt + the output from the previous step.
4. Repeat until Step 8.

See [README.md](README.md) for the full operator guide.
