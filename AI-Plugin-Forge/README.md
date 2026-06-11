# AI Plugin Forge

A starter automation project for generating unique Minecraft Java Edition Paper/Spigot plugins with:

- ChatGPT as coordinator/spec judge
- Gemini as creative originality generator
- DeepSeek as Java/Paper code generator
- Local Gradle build to produce the final `.jar`

## Setup

1. Install:
   - Python 3.11+
   - Java 21
   - Gradle
   - Git, optional but recommended

2. Open a terminal in this folder.

3. Create a virtual environment:

   Windows PowerShell:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env` and add your API keys.

   Do not share `.env`.

5. Run:

   ```powershell
   python forge.py "Make me a unique Minecraft Paper plugin"
   ```

6. If the build passes, the jar should appear in:

   ```text
   finished/
   ```

## What it does

1. Asks Gemini for original plugin ideas.
2. Asks DeepSeek for original plugin ideas.
3. Asks ChatGPT to choose the final plugin spec.
4. Asks DeepSeek to generate the full Paper/Gradle project.
5. Writes the generated plugin into `work/`.
6. Runs Gradle.
7. If build succeeds, copies the jar into `finished/`.
8. If build fails, sends the build errors back to DeepSeek for corrections.

## Important

This is a starter forge, not a polished finished product yet. Generated plugins should be tested on a local/test server before being used on a live server.
