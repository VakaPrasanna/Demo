# #!/usr/bin/env python3
# """
# Enhanced Jenkins Declarative Pipeline -> GitHub Actions converter
# - Parses a Jenkinsfile (declarative syntax)
# - Produces .github/workflows/ci.yml with composite actions for each stage
# - Fixed ordering of runs-on and container properties
# - Comprehensive handling of agent, images, parameters, environment, and post stages

# New Features:
# - Generates composite actions for every stage
# - Proper handling of parameters
# - Enhanced agent and container support
# - Improved post-stage handling
# - Better environment variable management
# """

import os
import re
import sys
import yaml
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

# ----------------------------
# Helpers
# ----------------------------

def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*", "", text)
    return text

def find_block(text: str, start_pat: str) -> Tuple[int, int]:
    m = re.search(start_pat, text)
    if not m:
        return -1, -1
    i = m.end()
    while i < len(text) and text[i].isspace():
        i += 1
    if i >= len(text) or text[i] != '{':
        return -1, -1
    depth = 0
    start = i + 1
    i += 1
    while i < len(text):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            if depth == 0:
                return start, i
            depth -= 1
        i += 1
    return -1, -1

def sanitize_name(name: str) -> str:
    """Sanitize names for file paths and action names"""
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name.strip())

def gha_job_id(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip()).strip("-").lower()
    return slug or "job"

# ---------- Parameters ----------

def extract_parameters(pipeline_body: str) -> Dict[str, Any]:
    """Extract pipeline parameters"""
    params = {}
    s, e = find_block(pipeline_body, r"\bparameters\b")
    if s == -1:
        return params
    
    param_body = pipeline_body[s:e]
    
    # string parameters
    for m in re.finditer(r"string\s*\(\s*name\s*:\s*['\"]([^'\"]+)['\"](?:,\s*defaultValue\s*:\s*['\"]([^'\"]*)['\"])?(?:,\s*description\s*:\s*['\"]([^'\"]*)['\"])?", param_body):
        name = m.group(1)
        default = m.group(2) or ""
        description = m.group(3) or ""
        params[name] = {
            "type": "string",
            "default": default,
            "description": description
        }
    
    # boolean parameters
    for m in re.finditer(r"booleanParam\s*\(\s*name\s*:\s*['\"]([^'\"]+)['\"](?:,\s*defaultValue\s*:\s*(true|false))?(?:,\s*description\s*:\s*['\"]([^'\"]*)['\"])?", param_body):
        name = m.group(1)
        default = m.group(2) or "false"
        description = m.group(3) or ""
        params[name] = {
            "type": "boolean",
            "default": default.lower() == "true",
            "description": description
        }
    
    # choice parameters
    for m in re.finditer(r"choice\s*\(\s*name\s*:\s*['\"]([^'\"]+)['\"](?:,\s*choices\s*:\s*\[([^\]]+)\])?(?:,\s*description\s*:\s*['\"]([^'\"]*)['\"])?", param_body):
        name = m.group(1)
        choices_str = m.group(2) or ""
        description = m.group(3) or ""
        choices = [c.strip().strip('\'"') for c in choices_str.split(',') if c.strip()]
        params[name] = {
            "type": "choice",
            "options": choices,
            "default": choices[0] if choices else "",
            "description": description
        }
    
    return params

# ---------- Agents (global + stage) ----------

def extract_global_agent(pipeline_body: str) -> Dict[str, Any]:
    """
    Returns one of:
      {"type":"any"}
      {"type":"label","label":"linux"}
      {"type":"docker","image":"node:20","args":"--cpus=2"}
      {} if not present
    """
    s, e = find_block(pipeline_body, r"\bagent\b")
    if s == -1:
        return {}
    agent_body = pipeline_body[s:e]
    
    # agent any
    if re.search(r"\bany\b", agent_body):
        return {"type": "any"}
    
    # agent { label '...' }
    m = re.search(r"label\s+['\"]([^'\"]+)['\"]", agent_body)
    if m:
        return {"type": "label", "label": m.group(1).strip()}
    
    # agent { docker { image '...' (args '...')? } }
    ds, de = find_block(agent_body, r"\bdocker\b")
    if ds != -1:
        docker_body = agent_body[ds:de]
        img = re.search(r"image\s+['\"]([^'\"]+)['\"]", docker_body)
        args = re.search(r"args\s+['\"]([^'\"]+)['\"]", docker_body)
        if img:
            out = {"type": "docker", "image": img.group(1).strip()}
            if args:
                out["args"] = args.group(1).strip()
            return out
    return {}

def extract_stage_agent(stage_body: str) -> Dict[str, Any]:
    s, e = find_block(stage_body, r"\bagent\b")
    if s == -1:
        return {}
    body = stage_body[s:e]
    if re.search(r"\bany\b", body):
        return {"type": "any"}
    m = re.search(r"label\s+['\"]([^'\"]+)['\"]", body)
    if m:
        return {"type": "label", "label": m.group(1).strip()}
    ds, de = find_block(body, r"\bdocker\b")
    if ds != -1:
        dbody = body[ds:de]
        img = re.search(r"image\s+['\"]([^'\"]+)['\"]", dbody)
        args = re.search(r"args\s+['\"]([^'\"]+)['\"]", dbody)
        if img:
            out = {"type": "docker", "image": img.group(1).strip()}
            if args:
                out["args"] = args.group(1).strip()
            return out
    return {}

def map_label_to_runs_on(label: str) -> Any:
    """Best-effort mapping. Unknown labels -> self-hosted runner label array."""
    normalized = label.strip().lower()
    # common github-hosted labels
    if normalized in ("ubuntu", "ubuntu-latest"):
        return "ubuntu-latest"
    if normalized in ("windows", "windows-latest"):
        return "windows-latest"
    if normalized in ("mac", "macos", "macos-latest"):
        return "macos-latest"
    # fallback: self-hosted with label
    return ["self-hosted", label]

# ---------- Environment and Pipeline structure ----------

def extract_env_kv(env_body: str) -> Dict[str, str]:
    env: Dict[str, str] = {}
    for line in env_body.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)", line)
        if m:
            key = m.group(1)
            val = m.group(2).strip()
            if (val.startswith("'") and val.endswith("'")) or (val.startswith('"') and val.endswith('"')):
                val = val[1:-1]
            env[key] = val
    return env

def split_stages(stages_body: str) -> List[Dict[str, Any]]:
    res = []
    i = 0
    while True:
        m = re.search(r"stage\s*\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\{", stages_body[i:])
        if not m:
            break
        name = m.group(1)
        abs_start = i + m.start()
        block_start = abs_start + m.end() - m.start() - 1
        depth = 0
        j = block_start + 1
        content_start = j
        while j < len(stages_body):
            if stages_body[j] == '{':
                depth += 1
            elif stages_body[j] == '}':
                if depth == 0:
                    res.append({"name": name, "content": stages_body[content_start:j]})
                    i = j + 1
                    break
                depth -= 1
            j += 1
        else:
            break
    return res

def extract_stage_when_branch(stage_body: str) -> str:
    s, e = find_block(stage_body, r"\bwhen\b")
    if s == -1:
        return ""
    when_body = stage_body[s:e]
    m = re.search(r"branch\s+['\"]([^'\"]+)['\"]", when_body)
    return m.group(1) if m else ""

def extract_stage_environment(stage_body: str) -> Dict[str, str]:
    s, e = find_block(stage_body, r"\benvironment\b")
    if s == -1:
        return {}
    return extract_env_kv(stage_body[s:e])

def multiline_to_commands(s: str) -> List[str]:
    lines = [ln.strip() for ln in s.splitlines()]
    return [ln for ln in lines if ln]

def extract_steps_commands(stage_body: str) -> List[str]:
    cmds: List[str] = []
    s, e = find_block(stage_body, r"\bsteps\b")
    search_zone = stage_body[s:e] if s != -1 else stage_body
    zone = strip_comments(search_zone)

    for m in re.finditer(r"sh\s+([\"']{3})([\s\S]*?)\1", zone):
        inner = m.group(2)
        cmds.extend(multiline_to_commands(inner))
    for m in re.finditer(r"sh\s+['\"]([^'\"]+)['\"]", zone):
        cmds.append(m.group(1).strip())
    for m in re.finditer(r"\becho\s+['\"]([^'\"]+)['\"]", zone):
        cmds.append(f"echo {m.group(1).strip()}")

    return cmds

# ---------- post blocks (stage + pipeline) ----------

def _extract_post_body(body: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    ps, pe = find_block(body, r"\bpost\b")
    if ps == -1:
        return out
    post_body = body[ps:pe]

    def _collect(kind: str) -> Dict[str, Any]:
        ks, ke = find_block(post_body, rf"\b{kind}\b")
        if ks == -1:
            return {}
        kbody = post_body[ks:ke]
        data: Dict[str, Any] = {}
        # archiveArtifacts (common)
        m = re.search(r"archiveArtifacts\s*\(\s*artifacts\s*:\s*['\"]([^'\"]+)['\"]", kbody)
        if m:
            data["archive"] = m.group(1).strip()
        # capture shell/echo inside post
        cmds = []
        for mm in re.finditer(r"sh\s+['\"]([^'\"]+)['\"]", kbody):
            cmds.append(mm.group(1).strip())
        for mm in re.finditer(r"sh\s+([\"']{3})([\s\S]*?)\1", kbody):
            cmds.extend(multiline_to_commands(mm.group(2)))
        for mm in re.finditer(r"\becho\s+['\"]([^'\"]+)['\"]", kbody):
            cmds.append(f"echo {mm.group(1).strip()}")
        if cmds:
            data["commands"] = cmds
        # mail to (placeholder)
        m = re.search(r"mail\s+to\s*:\s*['\"]([^'\"]+)['\"]", kbody)
        if m:
            data["mail_to"] = m.group(1).strip()
        return data

    for kind in ("always", "success", "failure", "cleanup"):
        kdata = _collect(kind)
        if kdata:
            out[kind] = kdata
    return out

def extract_stage_post(stage_body: str) -> Dict[str, Any]:
    return _extract_post_body(stage_body)

def extract_pipeline_post(pipeline_body: str) -> Dict[str, Any]:
    return _extract_post_body(pipeline_body)

def extract_parallel(stage_body: str) -> List[Dict[str, Any]]:
    ps, pe = find_block(stage_body, r"\bparallel\b")
    if ps == -1:
        return []
    par_body = stage_body[ps:pe]
    return split_stages(par_body)

# ---------- Composite Actions Generation ----------

def generate_composite_action(stage_name: str, commands: List[str], stage_env: Dict[str, str], 
                            stage_agent: Dict[str, Any], post_info: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a composite action for a stage"""
    action_def = {
        "name": f"{stage_name} Action",
        "description": f"Composite action for {stage_name} stage",
        "inputs": {},
        "runs": {
            "using": "composite",
            "steps": []
        }
    }
    
    # Add environment variables as inputs
    for env_key, env_val in stage_env.items():
        input_key = env_key.lower().replace('_', '-')
        action_def["inputs"][input_key] = {
            "description": f"Environment variable {env_key}",
            "required": False,
            "default": env_val
        }
    
    steps = []
    
    # Add main commands
    for i, cmd in enumerate(commands):
        step = {
            "name": f"Run command {i+1}",
            "run": cmd,
            "shell": "bash"
        }
        if stage_env:
            step["env"] = {k: f"${{{{ inputs.{k.lower().replace('_', '-')} }}}}" for k in stage_env.keys()}
        steps.append(step)
    
    # Add post steps
    for kind in ("always", "success", "failure"):
        if kind in post_info:
            pdata = post_info[kind]
            if "archive" in pdata:
                steps.append({
                    "name": f"Upload artifacts ({kind})",
                    "if": f"{kind}()",
                    "uses": "actions/upload-artifact@v4",
                    "with": {
                        "name": f"{sanitize_name(stage_name)}-{kind}-artifacts",
                        "path": pdata["archive"]
                    }
                })
            if "commands" in pdata:
                for cmd in pdata["commands"]:
                    steps.append({
                        "name": f"Post {kind}",
                        "if": f"{kind}()",
                        "run": cmd,
                        "shell": "bash"
                    })
    
    action_def["runs"]["steps"] = steps
    return action_def

def save_composite_actions(stages_info: List[Dict[str, Any]], output_dir: Path) -> List[str]:
    """Save composite actions to files and return their paths"""
    actions_dir = output_dir / ".github" / "actions"
    actions_dir.mkdir(parents=True, exist_ok=True)
    
    action_paths = []
    
    for stage_info in stages_info:
        stage_name = stage_info["name"]
        action_name = sanitize_name(stage_name.lower())
        action_dir = actions_dir / action_name
        action_dir.mkdir(exist_ok=True)
        
        action_def = generate_composite_action(
            stage_name,
            stage_info["commands"],
            stage_info.get("env", {}),
            stage_info.get("agent", {}),
            stage_info.get("post", {})
        )
        
        action_file = action_dir / "action.yml"
        with action_file.open("w", encoding="utf-8") as f:
            yaml.dump(action_def, f, sort_keys=False, width=1000)
        
        relative_path = f"./.github/actions/{action_name}"
        action_paths.append({
            "name": stage_name,
            "path": relative_path,
            "env": stage_info.get("env", {})
        })
    
    return action_paths

# ----------------------------
# Main converter
# ----------------------------

def convert_jenkins_to_gha(jenkins_text: str, output_dir: Path = Path(".")) -> Dict[str, Any]:
    text = strip_comments(jenkins_text)

    # pipeline { ... }
    pstart, pend = find_block(text, r"\bpipeline\b")
    if pstart == -1:
        raise ValueError("Not a declarative Jenkins pipeline (no 'pipeline { ... }' found).")
    pipeline_body = text[pstart:pend]

    # Extract pipeline components
    global_agent = extract_global_agent(pipeline_body)
    parameters = extract_parameters(pipeline_body)
    
    # Global environment
    es, ee = find_block(pipeline_body, r"\benvironment\b")
    global_env = extract_env_kv(pipeline_body[es:ee]) if es != -1 else {}

    # Stages
    ss, se = find_block(pipeline_body, r"\bstages\b")
    if ss == -1:
        raise ValueError("No 'stages { ... }' found.")
    stages_list = split_stages(pipeline_body[ss:se])

    # Pipeline-level post
    pipeline_post = extract_pipeline_post(pipeline_body)

    # Determine default runs-on and container from global agent
    default_runs_on: Any = "ubuntu-latest"
    default_container: Optional[Dict[str, Any]] = None
    if global_agent:
        if global_agent["type"] == "any":
            default_runs_on = "ubuntu-latest"
        elif global_agent["type"] == "label":
            default_runs_on = map_label_to_runs_on(global_agent["label"])
        elif global_agent["type"] == "docker":
            default_runs_on = "ubuntu-latest"
            default_container = {"image": global_agent["image"]}
            if "args" in global_agent:
                default_container["options"] = global_agent["args"]

    # Build workflow inputs from parameters
    workflow_inputs = {}
    workflow_env = dict(global_env)  # Start with global env
    
    for param_name, param_info in parameters.items():
        if param_info["type"] == "string":
            workflow_inputs[param_name] = {
                "description": param_info["description"] or f"Parameter {param_name}",
                "required": False,
                "default": param_info["default"],
                "type": "string"
            }
        elif param_info["type"] == "boolean":
            workflow_inputs[param_name] = {
                "description": param_info["description"] or f"Parameter {param_name}",
                "required": False,
                "default": param_info["default"],
                "type": "boolean"
            }
        elif param_info["type"] == "choice":
            workflow_inputs[param_name] = {
                "description": param_info["description"] or f"Parameter {param_name}",
                "required": False,
                "default": param_info["default"],
                "type": "choice",
                "options": param_info["options"]
            }

    # Base GHA structure
    gha: Dict[str, Any] = {
        "name": "CI",
        "on": {
            "push": {"branches": ["master", "main"]},
            "pull_request": {},
        }
    }
    
    # Add workflow_dispatch with inputs if parameters exist
    if workflow_inputs:
        gha["on"]["workflow_dispatch"] = {"inputs": workflow_inputs}
    
    # Add global environment
    if workflow_env:
        gha["env"] = workflow_env

    gha["jobs"] = {}

    # Collect stage information for composite actions
    stages_info = []
    last_job_ids: List[str] = []
    prev_job_id: str = ""

    def compute_job_env(stage_env: Dict[str, str]) -> Dict[str, str]:
        """Return only keys that differ from workflow-level env or are new."""
        if not stage_env:
            return {}
        if not global_env:
            return stage_env
        out: Dict[str, str] = {}
        for k, v in stage_env.items():
            if k not in global_env or str(global_env[k]) != str(v):
                out[k] = v
        return out

    def apply_agent_to_job(job_def: Dict[str, Any], stage_agent: Dict[str, Any]):
        """Apply agent configuration to job definition with proper ordering"""
        # FIXED: Set runs-on first, then container
        if not stage_agent:
            # inherit global defaults
            job_def["runs-on"] = default_runs_on
            if default_container:
                job_def["container"] = dict(default_container)
            return
            
        if stage_agent["type"] == "any":
            job_def["runs-on"] = "ubuntu-latest"
        elif stage_agent["type"] == "label":
            job_def["runs-on"] = map_label_to_runs_on(stage_agent["label"])
        elif stage_agent["type"] == "docker":
            job_def["runs-on"] = "ubuntu-latest"
            job_def["container"] = {"image": stage_agent["image"]}
            if "args" in stage_agent:
                job_def["container"]["options"] = stage_agent["args"]

    def create_job_steps_with_composite(stage_name: str, action_path: str, stage_env: Dict[str, str]) -> List[Dict[str, Any]]:
        """Create job steps using composite action"""
        steps = [{"uses": "actions/checkout@v4"}]
        
        # Add composite action step
        step = {
            "name": f"Run {stage_name}",
            "uses": action_path
        }
        
        # Add inputs for environment variables
        if stage_env:
            step["with"] = {k.lower().replace('_', '-'): f"${{{{ env.{k} }}}}" for k in stage_env.keys()}
        
        steps.append(step)
        return steps

    # Process stages
    for stage in stages_list:
        stage_name = stage["name"]
        stage_body = stage["content"]

        # Handle parallel stages
        parallel_substages = extract_parallel(stage_body)
        if parallel_substages:
            upstream = prev_job_id or (last_job_ids[-1] if last_job_ids else None)
            parallel_ids = []
            
            for sub in parallel_substages:
                sub_name = sub["name"]
                sub_body = sub["content"]
                job_id = gha_job_id(sub_name)
                parallel_ids.append(job_id)

                stage_agent = extract_stage_agent(sub_body)
                stage_env_raw = extract_stage_environment(sub_body)
                job_env = compute_job_env(stage_env_raw)
                branch = extract_stage_when_branch(sub_body)
                if_cond = f"github.ref == 'refs/heads/{branch}'" if branch else None
                commands = extract_steps_commands(sub_body)
                post_info = extract_stage_post(sub_body)

                # Add to stages info for composite action generation
                stages_info.append({
                    "name": sub_name,
                    "commands": commands,
                    "env": stage_env_raw,
                    "agent": stage_agent,
                    "post": post_info
                })

                # Create job definition with proper ordering
                job_def: Dict[str, Any] = {}
                apply_agent_to_job(job_def, stage_agent)  # Sets runs-on and container
                
                if job_env:
                    job_def["env"] = job_env
                if if_cond:
                    job_def["if"] = if_cond
                if upstream:
                    job_def["needs"] = upstream
                
                # Will be updated after composite actions are created
                job_def["steps"] = [{"uses": "actions/checkout@v4"}]
                
                gha["jobs"][job_id] = job_def

            last_job_ids = parallel_ids
            prev_job_id = ""
            continue

        # Handle sequential stages
        job_id = gha_job_id(stage_name)
        stage_agent = extract_stage_agent(stage_body)
        stage_env_raw = extract_stage_environment(stage_body)
        job_env = compute_job_env(stage_env_raw)
        branch = extract_stage_when_branch(stage_body)
        if_cond = f"github.ref == 'refs/heads/{branch}'" if branch else None
        commands = extract_steps_commands(stage_body)
        post_info = extract_stage_post(stage_body)

        # Add to stages info for composite action generation
        stages_info.append({
            "name": stage_name,
            "commands": commands,
            "env": stage_env_raw,
            "agent": stage_agent,
            "post": post_info
        })

        # Create job definition with proper ordering
        job_def: Dict[str, Any] = {}
        apply_agent_to_job(job_def, stage_agent)  # Sets runs-on and container first
        
        if job_env:
            job_def["env"] = job_env
        if if_cond:
            job_def["if"] = if_cond

        if last_job_ids:
            job_def["needs"] = last_job_ids
            last_job_ids = []
        elif prev_job_id:
            job_def["needs"] = prev_job_id

        # Will be updated after composite actions are created
        job_def["steps"] = [{"uses": "actions/checkout@v4"}]
        
        gha["jobs"][job_id] = job_def
        prev_job_id = job_id

    # Generate composite actions
    action_paths = save_composite_actions(stages_info, output_dir)
    
    # Update job steps to use composite actions
    job_keys = list(gha["jobs"].keys())
    for i, job_key in enumerate(job_keys):
        if i < len(action_paths):
            action_info = action_paths[i]
            stage_env = action_info["env"]
            
            # Update steps to use composite action
            gha["jobs"][job_key]["steps"] = create_job_steps_with_composite(
                action_info["name"],
                action_info["path"],
                stage_env
            )

    # Pipeline-level post -> final job that depends on all others
    if pipeline_post:
        post_job_steps: List[Dict[str, Any]] = [{"uses": "actions/checkout@v4"}]
        
        for kind in ("always", "success", "failure", "cleanup"):
            if kind in pipeline_post:
                pdata = pipeline_post[kind]
                if "archive" in pdata:
                    post_job_steps.append({
                        "name": f"Upload artifacts ({kind})",
                        "if": f"{kind}()",
                        "uses": "actions/upload-artifact@v4",
                        "with": {"name": f"pipeline-{kind}-artifacts", "path": pdata["archive"]}
                    })
                if "commands" in pdata:
                    post_job_steps.append({
                        "name": f"Pipeline post {kind}",
                        "if": f"{kind}()",
                        "run": "\n".join(pdata["commands"])
                    })
                if "mail_to" in pdata:
                    post_job_steps.append({
                        "name": f"Notify on {kind}",
                        "if": f"{kind}()",
                        "run": f'echo "Replace with mail action to: {pdata.get("mail_to","")}"'
                    })
        
        if len(post_job_steps) > 1:  # More than just checkout
            all_jobs = [k for k in gha["jobs"].keys() if k != "pipeline-post"]
            post_job_def = {
                "name": "Pipeline Post",
                "runs-on": default_runs_on,
                "needs": all_jobs,
                "if": "always()",
                "steps": post_job_steps
            }
            if default_container:
                post_job_def["container"] = dict(default_container)
            gha["jobs"]["pipeline-post"] = post_job_def

    return gha

# ----------------------------
# CLI
# ----------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python converter.py <path/to/Jenkinsfile> [output_directory]")
        print("  output_directory: Where to create .github/workflows/ci.yml and .github/actions/")
        sys.exit(1)

    in_path = Path(sys.argv[1])
    if not in_path.exists():
        print(f"File not found: {in_path}")
        sys.exit(1)

    output_dir = Path(sys.argv[2]) if len(sys.argv) >= 3 else Path(".")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    workflow_path = output_dir / ".github" / "workflows" / "ci.yml"
    workflow_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        jenkins_text = in_path.read_text(encoding="utf-8")
        print(f"Converting {in_path} to GitHub Actions...")
        
        gha = convert_jenkins_to_gha(jenkins_text, output_dir)
        
        with workflow_path.open("w", encoding="utf-8") as f:
            yaml.dump(gha, f, sort_keys=False, width=1000)
        
        print(f" Main workflow saved to: {workflow_path}")
        print(f" Composite actions saved to: {output_dir / '.github' / 'actions'}")
        print("\nGenerated files:")
        print(f"  - {workflow_path.relative_to(output_dir)}")
        
        # List generated composite actions
        actions_dir = output_dir / ".github" / "actions"
        if actions_dir.exists():
            for action_dir in actions_dir.iterdir():
                if action_dir.is_dir():
                    action_file = action_dir / "action.yml"
                    if action_file.exists():
                        print(f"  - {action_file.relative_to(output_dir)}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
