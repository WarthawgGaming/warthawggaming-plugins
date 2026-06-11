import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.resolve()
PROMPTS = ROOT / "prompts"
WORK = ROOT / "work"
FINISHED = ROOT / "finished"


def read_prompt(name: str) -> str:
    return (PROMPTS / name).read_text(encoding="utf-8")


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing {name}. Copy .env.example to .env and fill it in.")
    return value


def call_openai(prompt: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=require_env("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", "gpt-5.5")
    response = client.responses.create(
        model=model,
        input=prompt,
    )
    return response.output_text


def call_gemini(prompt: str) -> str:
    from google import genai
    client = genai.Client(api_key=require_env("GEMINI_API_KEY"))
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )
    return response.text


def call_deepseek(prompt: str) -> str:
    from openai import OpenAI
    client = OpenAI(
        api_key=require_env("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
    )
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a Java/Paper Minecraft plugin developer. Follow the requested output format exactly."},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content


def extract_json(text: str) -> dict:
    """Best-effort JSON extraction if a model wraps output in markdown."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model response.")
    return json.loads(text[start:end + 1])


def write_project(project_name: str, files: list[dict]) -> Path:
    project_dir = WORK / project_name
    if project_dir.exists():
        shutil.rmtree(project_dir)
    project_dir.mkdir(parents=True)

    for f in files:
        path = project_dir / f["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f["content"], encoding="utf-8")

    return project_dir


def run_build(project_dir: Path) -> tuple[bool, str]:
    if (project_dir / "gradlew.bat").exists() and os.name == "nt":
        cmd = ["cmd", "/c", "gradlew.bat", "build"]
    elif (project_dir / "gradlew").exists():
        cmd = ["./gradlew", "build"]
    else:
        cmd = ["gradle", "build"]

    proc = subprocess.run(
        cmd,
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=180,
    )
    output = proc.stdout + "\n" + proc.stderr
    return proc.returncode == 0, output


def copy_jar(project_dir: Path) -> Path | None:
    jar_dir = project_dir / "build" / "libs"
    if not jar_dir.exists():
        return None
    jars = sorted(jar_dir.glob("*.jar"))
    if not jars:
        return None
    FINISHED.mkdir(exist_ok=True)
    target = FINISHED / jars[-1].name
    shutil.copy2(jars[-1], target)
    return target


def main():
    load_dotenv(ROOT / ".env")

    request = " ".join(sys.argv[1:]).strip()
    if not request:
        print('Usage: python forge.py "Make me a unique Minecraft Paper plugin"')
        sys.exit(1)

    print("AI Plugin Forge starting...")
    print("Request:", request)

    idea_prompt = read_prompt("idea_prompt.txt") + "\n\nUser request:\n" + request

    print("\n[1/7] Asking Gemini for original ideas...")
    gemini_ideas = call_gemini(idea_prompt)
    (ROOT / "last_gemini_ideas.txt").write_text(gemini_ideas, encoding="utf-8")

    print("[2/7] Asking DeepSeek for original ideas...")
    deepseek_ideas = call_deepseek(idea_prompt)
    (ROOT / "last_deepseek_ideas.txt").write_text(deepseek_ideas, encoding="utf-8")

    judge_prompt = (
        read_prompt("judge_prompt.txt")
        + "\n\nUser request:\n" + request
        + "\n\nGEMINI IDEAS:\n" + gemini_ideas
        + "\n\nDEEPSEEK IDEAS:\n" + deepseek_ideas
    )

    print("[3/7] Asking ChatGPT to choose final plugin spec...")
    final_spec = call_openai(judge_prompt)
    (ROOT / "last_final_spec.txt").write_text(final_spec, encoding="utf-8")

    code_prompt = read_prompt("code_prompt.txt") + "\n\nAPPROVED SPEC:\n" + final_spec

    print("[4/7] Asking DeepSeek to generate full project files...")
    code_json_text = call_deepseek(code_prompt)
    (ROOT / "last_code_response.txt").write_text(code_json_text, encoding="utf-8")
    project = extract_json(code_json_text)

    plugin_name = project.get("plugin_name", "GeneratedPlugin").replace(" ", "")
    project_dir = write_project(plugin_name, project["files"])

    print(f"[5/7] Project written to {project_dir}")

    max_fix_attempts = 3
    for attempt in range(max_fix_attempts + 1):
        print(f"[6/7] Running Gradle build, attempt {attempt + 1}...")
        ok, build_log = run_build(project_dir)
        (project_dir / f"build_attempt_{attempt + 1}.log").write_text(build_log, encoding="utf-8")

        if ok:
            jar = copy_jar(project_dir)
            print("[7/7] Build passed.")
            if jar:
                print(f"Jar saved to: {jar}")
            else:
                print("Build passed but no jar was found in build/libs.")
            return

        print("Build failed.")
        if attempt >= max_fix_attempts:
            print("No more fix attempts. Check the build log:")
            print(project_dir / f"build_attempt_{attempt + 1}.log")
            return

        file_list = "\n".join(
            str(p.relative_to(project_dir))
            for p in project_dir.rglob("*")
            if p.is_file()
        )
        fix_prompt = (
            read_prompt("fix_errors_prompt.txt")
            + "\n\nPROJECT FILE LIST:\n"
            + file_list
            + "\n\nBUILD ERRORS:\n"
            + build_log[-12000:]
        )

        print("Asking DeepSeek for build fixes...")
        fix_json_text = call_deepseek(fix_prompt)
        (project_dir / f"fix_response_{attempt + 1}.txt").write_text(fix_json_text, encoding="utf-8")
        fixes = extract_json(fix_json_text)

        for f in fixes.get("files", []):
            path = project_dir / f["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f["content"], encoding="utf-8")

    print("Finished.")


if __name__ == "__main__":
    main()
