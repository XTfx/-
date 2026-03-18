---
name: switch-model
description: Switch the Claude model used in the current conversation while preserving chat context. Invoke when user wants to change model (e.g. "switch to opus", "use haiku", "/switch-model sonnet"). Supports aliases: haiku, sonnet, opus.
---

# Model Switching Skill

Switch between Claude models without losing your conversation context.

## How It Works

Claude Code stores conversation history in a transcript file. The `claude --continue` command resumes the last session with full context. By updating the model config before resuming, you effectively switch models while keeping your entire chat history.

## Supported Models

| Alias  | Model ID                          | Best For                          |
|--------|-----------------------------------|-----------------------------------|
| haiku  | claude-haiku-4-5-20251001         | Fast, lightweight tasks           |
| sonnet | claude-sonnet-4-6                 | Balanced (default)                |
| opus   | claude-opus-4-6                   | Complex reasoning & deep analysis |

## Workflow

Make a todo list and work through these steps one by one.

### 1. Parse the requested model

Read the user's request from the skill args or their last message. Accept:
- Short aliases: `haiku`, `sonnet`, `opus`
- Partial model IDs (case-insensitive match)
- Full model IDs

Map to canonical model ID:
```
haiku  → claude-haiku-4-5-20251001
sonnet → claude-sonnet-4-6
opus   → claude-opus-4-6
```

If no model is specified or the input is ambiguous, show the table above and ask the user to choose.

### 2. Check the current model

Run:
```bash
claude config get model
```

If the current model already matches the requested model, tell the user and stop — no action needed.

### 3. Update the model config

Run:
```bash
claude config set model <MODEL_ID>
```

Verify with:
```bash
claude config get model
```

### 4. Detect the environment and explain how to activate the change

IMPORTANT: The model change takes effect in the NEXT session, not the current one.

First, detect whether the user is on **mobile/web** or **desktop CLI**:
- Mobile/web indicators: user mentioned phone/mobile, no terminal access, can't use Ctrl+C, using browser
- CLI indicators: user is in a terminal, can run commands

Then give the appropriate instructions:

---

**If on desktop CLI:**

**Model switched to `<MODEL_ID>`.**

To activate the new model while keeping your full conversation history:

1. Press **Ctrl+C** (or type `/exit`) to end this session
2. Run `claude --continue` in your terminal to resume with `<MODEL_ID>`

Your entire conversation history will be preserved.

---

**If on mobile or web browser:**

**Model switched to `<MODEL_ID>`.**

To activate the new model:

1. Tap the **menu / settings icon** (top-right corner) and choose **"End session"** or **"New session"**, OR simply **close this tab/app**
2. Reopen Claude Code — it will automatically continue your last conversation with `<MODEL_ID>`

If there is no "End session" option, just **close and reopen** the app/tab. Your conversation history is saved automatically.

---

### 5. Optional — Compact first (for very long conversations)

If the conversation is very long, suggest the user run `/compact` before switching. This summarizes the context, which:
- Reduces token usage with the new model
- Speeds up the session resume
- Preserves all key information

Only suggest this if not already compacted.

## Error Handling

- **Unknown model name**: List the supported aliases and ask the user to pick one.
- **`claude config set` fails**: Show the error output and suggest the user manually edit `~/.claude.json` or run the command themselves.
- **User wants to switch back**: The same skill works in reverse — just call `/switch-model <previous-model>`.

## Example Interactions

**User:** `/switch-model opus`
→ Run `claude config set model claude-opus-4-6`, confirm, then instruct user to `Ctrl+C` + `claude --continue`.

**User:** `switch to haiku, it's a simple task`
→ Run `claude config set model claude-haiku-4-5-20251001`, confirm, instruct on how to resume.

**User:** `/switch-model`  (no arg)
→ Show model table and ask which model they want.
