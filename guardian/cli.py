"""
Guardian CLI - Command Line Interface
Entry point for all Guardian commands.

Commands:
    guardian status            System + project health report
    guardian version           Print version
    guardian chat              Interactive AI chat session
    guardian memory list       Show stored memories
    guardian memory remember   Store a semantic fact
    guardian memory search     Search episodic history
    guardian memory forget     Delete a specific memory
    guardian memory clear      Delete all memories (with confirmation)
"""

import logging
import time
import uuid
from typing import Optional, List, Dict

log = logging.getLogger(__name__)

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from guardian import __phase__, __version__
from guardian.core.status import collect_status

app = typer.Typer(
    name="guardian",
    help="AI Guardian - Personal AI System",
    no_args_is_help=True,
)

memory_app = typer.Typer(
    name="memory",
    help="Manage Guardian long-term memory",
    no_args_is_help=True,
)
app.add_typer(memory_app, name="memory")

skills_app = typer.Typer(
    name="skills",
    help="List and inspect Guardian skill modes",
    no_args_is_help=True,
)
app.add_typer(skills_app, name="skills")

tools_app = typer.Typer(
    name="tools",
    help="List Guardian tools and run workspace operations",
    no_args_is_help=True,
)
app.add_typer(tools_app, name="tools")

security_app = typer.Typer(
    name="security",
    help="Security Guardian: scan, audit, and track threats",
    no_args_is_help=True,
)
app.add_typer(security_app, name="security")

canary_app = typer.Typer(
    name="canary",
    help="Canary & Honeypot System: plant decoys, monitor leaks and tampering",
    no_args_is_help=True,
)
security_app.add_typer(canary_app, name="canary")

knowledge_app = typer.Typer(
    name="knowledge",
    help="Knowledge Layer: ingest documents and query the knowledge base",
    no_args_is_help=True,
)
app.add_typer(knowledge_app, name="knowledge")

models_app = typer.Typer(
    name="models",
    help="Twenty-Slot Model Foundation (Architecture 2.0) and Task Router",
    no_args_is_help=True,
)
app.add_typer(models_app, name="models")

web_app = typer.Typer(
    name="web",
    help="Digital Access Layer: safe web discovery, page retrieval, and research",
    no_args_is_help=True,
)
app.add_typer(web_app, name="web")

permissions_app = typer.Typer(
    name="permissions",
    help="Permission & Operational Safety Layer: Level 1/2/3 gates and audit logs",
    no_args_is_help=True,
)
app.add_typer(permissions_app, name="permissions")

mcp_app = typer.Typer(
    name="mcp",
    help="Model Context Protocol server for external clients",
    no_args_is_help=True,
)
app.add_typer(mcp_app, name="mcp")

guardrails_app = typer.Typer(
    name="guardrails",
    help="LLM security guardrails: scan inputs/outputs for threats",
    no_args_is_help=True,
)
app.add_typer(guardrails_app, name="guardrails")

voice_app = typer.Typer(
    name="voice",
    help="Voice I/O: speech-to-text, text-to-speech, wake word",
    no_args_is_help=True,
)
app.add_typer(voice_app, name="voice")

gateway_app = typer.Typer(
    name="gateway",
    help="Hub Remote Gateway: WireGuard binding, pairing, and remote API",
    no_args_is_help=True,
)
app.add_typer(gateway_app, name="gateway")

pair_app = typer.Typer(
    name="pair",
    help="Device pairing lifecycle: initiate, list, approve, revoke",
    no_args_is_help=True,
)
gateway_app.add_typer(pair_app, name="pair")

console = Console(highlight=False)


def _ok(val: bool, yes: str = "YES", no: str = "no") -> str:
    return f"[green]{yes}[/green]" if val else f"[yellow]{no}[/yellow]"


def _render_status(status: dict) -> None:
    console.print()
    console.print(Panel(
        Text.from_markup(
            f"[bold cyan]AI GUARDIAN[/bold cyan]  v{__version__}\n"
            f"[dim]{__phase__}[/dim]"
        ),
        box=box.DOUBLE, expand=False,
    ))
    console.print()

    g = status.get("guardian", {})
    t = Table(title="[bold]Guardian Project[/bold]", box=box.SIMPLE, show_header=False)
    t.add_column("Key", style="dim", width=22)
    t.add_column("Value")
    t.add_row("Version", g.get("version", "?"))
    t.add_row("Phase", g.get("phase", "?"))
    t.add_row("Root", g.get("root", "?"))
    t.add_row("Venv", _ok(g.get("venv_exists"), "present", "MISSING"))
    t.add_row("Constitution", _ok(g.get("constitution_exists"), "present", "MISSING"))
    t.add_row(".env file", _ok(g.get("env_file_exists"), "present", "not created"))
    console.print(t)

    py = status.get("python", {})
    t2 = Table(title="[bold]Python Runtime[/bold]", box=box.SIMPLE, show_header=False)
    t2.add_column("Key", style="dim", width=22)
    t2.add_column("Value")
    t2.add_row("Version", py.get("version", "?"))
    t2.add_row("Executable", py.get("executable", "?"))
    console.print(t2)

    pl = status.get("platform", {})
    t3 = Table(title="[bold]Hardware[/bold]", box=box.SIMPLE, show_header=False)
    t3.add_column("Key", style="dim", width=22)
    t3.add_column("Value")
    t3.add_row("OS", pl.get("os", "?"))
    t3.add_row("CPU", pl.get("cpu", "?"))
    t3.add_row("Cores", f"{pl.get('cpu_cores_physical','?')} physical / {pl.get('cpu_cores_logical','?')} logical")
    t3.add_row("RAM Total", f"{pl.get('ram_total_gb','?')} GB")
    t3.add_row("RAM Available", f"{pl.get('ram_available_gb','?')} GB")
    console.print(t3)

    gpu = status.get("gpu", {})
    t4 = Table(title="[bold]GPU[/bold]", box=box.SIMPLE, show_header=False)
    t4.add_column("Key", style="dim", width=22)
    t4.add_column("Value")
    if gpu.get("available") and gpu.get("gpus"):
        for i, g_info in enumerate(gpu["gpus"]):
            t4.add_row(f"GPU {i}", g_info.get("name", "?"))
            t4.add_row("  VRAM Total", f"{g_info.get('vram_total_mb','?')} MB")
            t4.add_row("  VRAM Free",  f"{g_info.get('vram_free_mb','?')} MB")
    else:
        t4.add_row("Status", gpu.get("status", "unavailable"))
    console.print(t4)

    git = status.get("git", {})
    t5 = Table(title="[bold]Git[/bold]", box=box.SIMPLE, show_header=False)
    t5.add_column("Key", style="dim", width=22)
    t5.add_column("Value")
    t5.add_row("Installed", _ok(git.get("installed")))
    t5.add_row("Repo initialized", _ok(git.get("repo_initialized")))
    if git.get("repo_initialized"):
        t5.add_row("Branch", git.get("branch", "?"))
        t5.add_row("Commits", str(git.get("commits", 0)))
    console.print(t5)

    mb = status.get("model_backends", {})
    backends = mb.get("backends", [])
    if backends:
        t6 = Table(title="[bold]Model Backends[/bold]", box=box.SIMPLE, show_header=False)
        t6.add_column("Key", style="dim", width=22)
        t6.add_column("Value")
        for b in backends:
            t6.add_row(b["name"], f"{_ok(b['available'])}  {b['model']}")
        t6.add_row("Active", f"{mb.get('available_count',0)}/{mb.get('total_count',0)}")
        console.print(t6)

    # Memory status
    try:
        from guardian.memory import get_memory_manager
        mm = get_memory_manager()
        ms = mm.status()
        t7 = Table(title="[bold]Memory[/bold]", box=box.SIMPLE, show_header=False)
        t7.add_column("Key", style="dim", width=22)
        t7.add_column("Value")
        t7.add_row("Database", str(ms["db_path"]))
        t7.add_row("Episodic records", str(ms["episodic_count"]))
        t7.add_row("Semantic facts", str(ms["semantic_count"]))
        console.print(t7)
    except Exception:
        pass

    cog = status.get("cognitive", {})
    if cog and "total_outcomes" in cog:
        t8 = Table(title="[bold]Cognitive Layer[/bold]", box=box.SIMPLE, show_header=False)
        t8.add_column("Key", style="dim", width=22)
        t8.add_column("Value")
        t8.add_row("Execution outcomes", str(cog.get("total_outcomes", 0)))
        profs = cog.get("proficiency", {})
        if profs:
            for k, v in profs.items():
                t8.add_row(f"Proficiency: {k}", str(v))
        console.print(t8)

    pred = status.get("predictive", {})
    if pred and "epss_cache" in pred:
        t9 = Table(title="[bold]Predictive Agents Layer[/bold]", box=box.SIMPLE, show_header=False)
        t9.add_column("Key", style="dim", width=22)
        t9.add_column("Value")
        
        epss_cache = pred.get("epss_cache", {})
        t9.add_row("EPSS Cache Entries", str(epss_cache.get("cached_entries", 0)))
        t9.add_row("Attack Path Coverage", str(pred.get("attack_path_coverage", 0)))
        t9.add_row("Anomaly Detector", "IsolationForest" if pred.get("anomaly_detector_active") else "Statistical Baseline")
        
        agents = pred.get("active_agents", {})
        if agents:
            for name, scope in agents.items():
                t9.add_row(f"Agent: {name}", ", ".join(scope))
        
        coding_mode = pred.get("coding_agent_mode")
        if coding_mode:
            t9.add_row("CodingAgent Mode", coding_mode)
            
        specialist = pred.get("specialist_model", {})
        if specialist:
            avail = "[green]YES[/green]" if specialist.get("available") else "[red]NO (Base model)[/red]"
            t9.add_row("Specialist Model", avail)
            if specialist.get("available"):
                t9.add_row("  Eval Delta", specialist.get("eval_delta", "N/A"))
                
        console.print(t9)


    const = status.get("constitution", {})
    if const:
        tc = Table(title="[bold]Constitution & Enforceability[/bold]", box=box.SIMPLE, show_header=False)
        tc.add_column("Key", style="dim", width=22)
        tc.add_column("Value")
        tc.add_row("Status", const.get("status", "Unknown"))
        if const.get("active"):
            tc.add_row("Expected Hash", const.get("expected", "?"))
            tc.add_row("Actual Hash", const.get("actual", "?"))
        console.print(tc)

    comp = status.get("compliance", {})
    if comp and "dsl_rules" in comp:
        tcomp = Table(title="[bold]Rules & Compliance[/bold]", box=box.SIMPLE, show_header=False)
        tcomp.add_column("Key", style="dim", width=22)
        tcomp.add_column("Value")
        tcomp.add_row("DSL Rules", str(comp.get("dsl_rules", 0)))
        tcomp.add_row("Detection Rules", str(comp.get("det_rules", 0)))
        refs = comp.get("refs", [])
        tcomp.add_row("Legal References", f"{len(refs)} (Stale: {sum(1 for r in refs if r.get('stale'))})")
        console.print(tcomp)
        
    collab = status.get("collab", {})
    if collab:
        tcollab = Table(title="[bold]Collaboration Protocol[/bold]", box=box.SIMPLE, show_header=False)
        tcollab.add_column("Key", style="dim", width=22)
        tcollab.add_column("Value")
        tcollab.add_row("Framework", collab.get("framework", "INACTIVE"))
        console.print(tcollab)

    lap = status.get("laptop", {})
    if lap:
        t = Table(title="[bold]Laptop Control[/bold]", box=box.SIMPLE, show_header=False)
        t.add_column("Key", style="dim", width=22)
        t.add_column("Value")
        t.add_row("Status", "[red]OFF (Feature Flag)[/red]" if not lap.get("enabled") else "[yellow]ENABLED[/yellow]")
        t.add_row("Kill Switch", f"[bold red]{lap.get('kill_switch')}[/bold red]")
        t.add_row("Blocklist", f"{lap.get('blocklist_size')} patterns")
        t.add_row("Allowlist", f"{lap.get('allowlist_size')} apps")
        t.add_row("Active Session", f"{lap.get('active_session')} ({lap.get('actions_used')} actions)")
        if "error" in lap:
            t.add_row("Error", f"[red]{lap['error']}[/red]")
        console.print(t)

    console.print(f"\n[dim]Timestamp: {status.get('timestamp', '?')}[/dim]")

    console.print()


# ─── Core commands ────────────────────────────────────────────────────────────

@app.command()
def status() -> None:
    """Report verified Guardian system and project status (Level 0 - observe only)."""
    try:
        data = collect_status()
        _render_status(data)
    except Exception as exc:
        console.print(f"[red]ERROR:[/red] Status collection failed: {exc}")
        raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Print Guardian version."""
    console.print(f"AI Guardian v{__version__} -- {__phase__}")


@app.command()
def chat(
    model: str = typer.Option("", "--model", "-m", help="Backend: groq, gemini, mock"),
    max_tokens: int = typer.Option(2048, "--max-tokens", help="Max tokens per response"),
    temperature: float = typer.Option(0.7, "--temperature", "-t", help="Sampling temperature"),
    no_memory: bool = typer.Option(False, "--no-memory", help="Disable memory for this session"),
    agentic: bool = typer.Option(False, "--agentic", "-a", help="Enable agentic tool use (model can call tools)"),
) -> None:
    """Start an interactive Guardian chat session."""
    from guardian.core.orchestrator import GuardianCore
    from guardian.core.session import Session
    from guardian.memory import get_memory_manager
    from guardian.model.registry import get_model
    from guardian.prompts import GUARDIAN_SYSTEM_PROMPT, GUARDIAN_MASTER_SYSTEM_PROMPT_V1
    from guardian.model.task_router import get_task_router
    from guardian.security.advisory import generate_firewall_advisory
    from guardian.skills import get_skill_router
    from guardian.skills import GUARDIAN_SKILL
    from guardian.tools import get_tool_executor
    from guardian.tools.loop import ToolLoop
    from guardian.tools.tool_call import TOOL_USE_SYSTEM_ADDITION

    # --- Task Router (Section 5 multi-model orchestration) ---
    _task_router = get_task_router()

    # --- Select backend ---
    try:
        prefer = model.strip().lower() if model.strip() else None
        backend = get_model(prefer=prefer)
        info = backend.get_info()
    except Exception as exc:
        console.print(f"[red]ERROR:[/red] No model backend available: {exc}")
        raise typer.Exit(code=1)

    # --- Memory ---
    mm = None
    session_id = str(uuid.uuid4())
    if not no_memory:
        try:
            mm = get_memory_manager()
            # Use Master System Prompt V1.0 (Section 1-18) as the active system prompt
            system_prompt = mm.build_system_prompt(GUARDIAN_MASTER_SYSTEM_PROMPT_V1)
        except Exception as exc:
            console.print(f"[yellow]Warning:[/yellow] Memory unavailable: {exc}")
            system_prompt = GUARDIAN_MASTER_SYSTEM_PROMPT_V1
    else:
        system_prompt = GUARDIAN_MASTER_SYSTEM_PROMPT_V1

    if agentic:
        system_prompt = system_prompt + "\n\n" + TOOL_USE_SYSTEM_ADDITION
        tool_executor = get_tool_executor()
        def _approve_callback(call):
            from guardian.tools import ToolLevel
            tool = tool_executor.get(call.name)
            if tool and tool.level == ToolLevel.READ:
                return True   # L0: auto-approve
            # L1/L2: ask user
            yn = console.input(f"[bold yellow]Tool:[/bold yellow] {call.summary()} -- Allow? [y/N] ").strip().lower()
            return yn == "y"
        tool_loop = ToolLoop(executor=tool_executor, approval_callback=_approve_callback)
    else:
        tool_executor = None
        tool_loop = None

    # --- Initialise core ---
    core = GuardianCore(
        model=backend,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    session = Session()
    skill_router = get_skill_router(system_prompt)
    active_skill = GUARDIAN_SKILL

    # --- Header ---
    mem_status = "[dim]Memory: OFF[/dim]" if no_memory else "[dim]Memory: ON[/dim]"
    agt_status = "[dim]Agentic: ON[/dim]" if agentic else "[dim]Agentic: OFF[/dim]"
    console.print()
    console.print(Panel(
        Text.from_markup(
            f"[bold cyan]AI GUARDIAN[/bold cyan]  v{__version__}  [dim]Master Prompt v1.0 ✓[/dim]\n"
            f"[dim]Model: {info.provider} / {info.model}[/dim]\n"
            f"{mem_status}  {agt_status}\n"
            f"[dim]Skills: auto-routed (scholar/builder/critic/tester)[/dim]\n"
            f"[dim]/exit  /clear  /status  /model  /skill  /route  /advisory[/dim]"
        ),
        box=box.DOUBLE, expand=False,
    ))
    console.print()

    # --- REPL ---
    while True:
        try:
            user_input = console.input("[bold green]You>[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Session ended.[/dim]")
            break

        if not user_input:
            continue

        # Slash commands
        if user_input.lower() in ("/exit", "/quit", "/q"):
            console.print(f"\n[dim]{session.summary()}[/dim]")
            console.print("[dim]Goodbye.[/dim]")
            break

        if user_input.lower() == "/clear":
            session.clear()
            console.print("[dim]Conversation history cleared.[/dim]")
            continue

        if user_input.lower() == "/status":
            console.print(f"[dim]{session.summary()}[/dim]")
            console.print(f"[dim]Model: {info.provider} / {info.model}[/dim]")
            console.print(f"[dim]Active skill: {active_skill.display_label()}[/dim]")
            try:
                from guardian.security import get_security_guardian, reset_security_guardian
                reset_security_guardian()
                sg = get_security_guardian()
                active_threats = sg.store.count_active()
                threat_str = f"[red]{active_threats} threat(s)[/red]" if active_threats > 0 else "[green]0 threats[/green]"
                console.print(f"[dim]Security: {threat_str}[/dim]")
            except Exception:
                pass
            if mm:
                ms = mm.status()
                ms_epi = ms['episodic_count']
            ms_sem = ms['semantic_count']
            console.print(f'[dim]Memory: {ms_epi} episodic | {ms_sem} facts[/dim]')
            continue

        if user_input.lower() == "/model":
            console.print(f"[dim]{info.provider} / {info.model} | local={info.is_local}[/dim]")
            continue

        if user_input.lower().startswith("/remember "):
            if mm:
                raw = user_input[len("/remember "):].strip()
                if "=" in raw:
                    k, _, v = raw.partition("=")
                    try:
                        mm.semantic.set(k.strip(), v.strip())
                        console.print(f"[dim]Remembered: {k.strip()!r} = {v.strip()!r}[/dim]")
                    except Exception as exc:
                        console.print(f"[red]Error:[/red] {exc}")
                else:
                    console.print("[dim]Usage: /remember key=value[/dim]")
            else:
                console.print("[dim]Memory is OFF for this session.[/dim]")
            continue

        if user_input.lower() == "/skill":
            console.print(f"[dim]Active skill: {active_skill.display_label()} | {active_skill.description}[/dim]")
            continue

        if user_input.lower().startswith("/skill "):
            from guardian.skills import get_skill_registry
            skill_name = user_input[7:].strip().lower()
            found = get_skill_registry().get(skill_name)
            if found:
                active_skill = found
                console.print(f"[dim]Skill set to: {active_skill.display_label()}[/dim]")
            else:
                console.print(f"[dim]Unknown skill {skill_name!r}. Available: guardian scholar builder critic tester[/dim]")
            continue

        if user_input.lower().startswith("/read "):
            from guardian.tools import ToolRequest, get_tool_executor
            tool_path = user_input[6:].strip()
            exe = get_tool_executor()
            res = exe.run(ToolRequest(name="file_read", params={"path": tool_path}))
            if res.success:
                console.print(Panel(res.output, title=f"[dim]file_read: {tool_path}[/dim]",
                    title_align="left", border_style="dim"))
                if res.truncated:
                    console.print("[yellow]Output truncated.[/yellow]")
            else:
                console.print(f"[red]Error:[/red] {res.error}")
            continue

        if user_input.lower().startswith("/ls"):
            from guardian.tools import ToolRequest, get_tool_executor
            ls_path = user_input[3:].strip() or "."
            exe = get_tool_executor()
            res = exe.run(ToolRequest(name="directory", params={"path": ls_path}))
            console.print(res.output if res.success else f"[red]{res.error}[/red]")
            continue

        if user_input.lower().startswith("/search "):
            from guardian.tools import ToolRequest, get_tool_executor
            search_term = user_input[8:].strip()
            exe = get_tool_executor()
            res = exe.run(ToolRequest(name="search", params={"pattern": search_term, "path": "."}))
            console.print(res.output if res.success else f"[red]{res.error}[/red]")
            continue

        if user_input.lower().startswith("/run "):
            from guardian.tools import ToolRequest, get_tool_executor
            cmd = user_input[5:].strip()
            console.print(f"\n[bold yellow]EXECUTE:[/bold yellow] {cmd}")
            confirm = console.input("[bold]Run this command? [y/N][/bold] ").strip().lower()
            if confirm == "y":
                exe = get_tool_executor()
                with console.status("[dim]Running...[/dim]", spinner="dots"):
                    res = exe.run(ToolRequest(
                        name="shell",
                        params={"command": cmd},
                        approved=True,
                        context="User-confirmed via /run in chat",
                    ))
                rc_val = res.metadata.get("returncode", "?")
                console.print(res.output if res.success else f"[red]Error (code {rc_val})[/red]\n{res.output}")
            else:
                console.print("[dim]Cancelled.[/dim]")
            continue

        if user_input.lower().startswith("/route "):
            # Section 5: Intelligent Task Routing — classify and select minimal model/tool set
            query_text = user_input[7:].strip()
            if not query_text:
                console.print("[dim]Usage: /route <query>[/dim]")
            else:
                try:
                    _rd = _task_router.route_request(query=query_text)
                    t = Table(title="[bold]Intelligent Task Router — Section 5[/bold]", box=box.SIMPLE)
                    t.add_column("Field", style="cyan")
                    t.add_column("Value")
                    d = _rd.to_dict()
                    t.add_row("Task Type", str(d.get("task_type", "")))
                    t.add_row("Selected Model / Tool", str(d.get("selected_model_or_tool", "")))
                    t.add_row("Selection Reason", str(d.get("selection_reason", "")))
                    t.add_row("Input Modalities", ", ".join(d.get("input_modalities", [])))
                    t.add_row("Output Modalities", ", ".join(d.get("output_modalities", [])))
                    collabs = [f"{c.get('role', '')}: {c.get('model', '')}" for c in d.get("collaborators", [])]
                    t.add_row("Collaborators (Sec 6)", ", ".join(collabs) or "None (single model sufficient)")
                    t.add_row("External Evidence", str(d.get("requires_external_evidence", False)))
                    t.add_row("Local Retrieval", str(d.get("requires_local_retrieval", False)))
                    console.print(t)
                    console.print(Panel(_rd.format_routing_report(), title="[dim]Routing Report (Section 17)[/dim]",
                        border_style="dim", expand=False))
                except Exception as exc:
                    console.print(f"[red]Route error:[/red] {exc}")
            continue

        if user_input.lower() == "/advisory":
            # Section 8: Defensive Security Advisory — interactive 8-point firewall advisory
            console.print("[bold cyan]Defensive Firewall Advisory — Section 8[/bold cyan]")
            console.print("[dim]Complete the 8-point schema (press Enter to skip optional fields):[/dim]\n")
            try:
                _ev  = console.input("[cyan]Evidence / trigger[/cyan]: ").strip() or "Suspicious traffic detected"
                _sd  = console.input("[cyan]Source -> Destination[/cyan]: ").strip() or "unknown -> internal"
                _pp  = console.input("[cyan]Protocol / Ports[/cyan]: ").strip() or "TCP/any"
                _out = console.input("[cyan]Intended outcome[/cyan]: ").strip() or "Block suspicious traffic"
                _imp = console.input("[cyan]Expected impact[/cyan]: ").strip() or "Prevent unauthorised access"
                _fp  = console.input("[cyan]Potential false positives[/cyan]: ").strip() or "None identified"
                _rb  = console.input("[cyan]Rollback plan[/cyan]: ").strip() or "Remove rule and restore default"
                _vp  = console.input("[cyan]Verification procedure[/cyan]: ").strip() or "Monitor logs for 24h"
                adv = generate_firewall_advisory(
                    evidence=_ev, src_dest=_sd, ports=_pp,
                    outcome=_out, impact=_imp, false_positives=_fp,
                    rollback=_rb, verification=_vp,
                )
                console.print(Panel(adv.format_markdown(), title="[dim]Advisory Report (Section 8)[/dim]",
                    border_style="cyan", expand=False))
            except (EOFError, KeyboardInterrupt):
                console.print("[dim]Advisory cancelled.[/dim]")
            except Exception as exc:
                console.print(f"[red]Advisory error:[/red] {exc}")
            continue

        if user_input.lower().startswith("/"):
            console.print("[dim]Commands: /exit /clear /status /model /remember key=value /skill [name] /route <query> /advisory /read <path> /ls [path] /search <term> /run <cmd>[/dim]")
            continue


        # --- Route to skill ---
        routing = skill_router.route(user_input, previous_skill=active_skill)
        if routing.switched:
            console.print(f"[dim]  Skill: {routing.label()}[/dim]")
        active_skill = routing.skill

        # --- Process (with optional tool loop) ---
        with console.status(f"[dim]{active_skill.icon} Thinking...[/dim]", spinner="dots"):
            if tool_loop:
                loop_result = tool_loop.run(
                    core, user_input, session,
                    active_skill=active_skill.name,
                    skill_prompt_addition=active_skill.prompt_addition,
                )
                response = loop_result.final_response
                # Show tool rounds to the user (transparency)
                for rnd in loop_result.rounds:
                    status = "OK" if rnd.success else "DENIED" if not rnd.approved else "FAIL"
                    console.print(f"[dim]  Tool [{rnd.round_number}] {rnd.call.name}: {status}[/dim]")
            else:
                response = core.process(
                    user_input, session,
                    active_skill=active_skill.name,
                    skill_prompt_addition=active_skill.prompt_addition,
                )

        if response.success:
            display_content = response.content

            # Auto-save to episodic memory
            if mm:
                try:
                    mm.episodic.save_turn(
                        session_id=session_id,
                        turn_number=response.session_turn,
                        user_message=user_input,
                        assistant_reply=display_content,
                        model_provider=response.model_provider,
                        model_name=response.model_name,
                        tokens_used=response.tokens_used,
                        duration_ms=response.duration_ms,
                    )
                except Exception:
                    pass  # Memory failure must never interrupt the conversation

            console.print()
            console.print(Panel(
                display_content,
                title=f"[dim]Guardian {active_skill.icon}[/dim]",
                title_align="left",
                border_style="dim",
                expand=False,
            ))
            console.print(
                f"[dim]  {active_skill.name} | "
                f"{response.model_name} | "
                f"{response.tokens_used} tokens | "
                f"{response.duration_s}s[/dim]\n"
            )
        else:
            console.print(f"[red]Error:[/red] {response.error}")


# ─── Memory commands ──────────────────────────────────────────────────────────

@memory_app.command("list")
def memory_list(
    limit: int = typer.Option(20, "--limit", "-n", help="Max records to show"),
    facts: bool = typer.Option(False, "--facts", "-f", help="Show semantic facts instead"),
) -> None:
    """List stored Guardian memories."""
    from guardian.memory import get_memory_manager
    mm = get_memory_manager()

    if facts:
        items = mm.semantic.list_all()
        if not items:
            console.print("[dim]No semantic facts stored.[/dim]")
            return
        t = Table(title="[bold]Stored Facts[/bold]", box=box.SIMPLE)
        t.add_column("Key", style="cyan")
        t.add_column("Value")
        t.add_column("Category", style="dim")
        t.add_column("Stored", style="dim")
        for f in items:
            t.add_row(f.key, f.value, f.category, f.timestamp.strftime("%Y-%m-%d"))
        console.print(t)
    else:
        records = mm.episodic.list_recent(limit)
        if not records:
            console.print("[dim]No episodic records stored.[/dim]")
            return
        t = Table(title=f"[bold]Recent Episodic Memory[/bold] (last {limit})", box=box.SIMPLE)
        t.add_column("ID", style="dim", width=10)
        t.add_column("When", style="dim", width=16)
        t.add_column("Model", style="dim", width=20)
        t.add_column("Message preview")
        for r in records:
            t.add_row(
                r.id[:8],
                r.timestamp.strftime("%m-%d %H:%M"),
                r.model_name,
                r.preview(60),
            )
        console.print(t)
        console.print(f"[dim]Total stored: {mm.episodic.count()}[/dim]")


@memory_app.command("remember")
def memory_remember(
    fact: str = typer.Argument(help='Fact to remember as "key=value"'),
    category: str = typer.Option("general", "--category", "-c",
                                  help="Category: preference, fact, project, general"),
) -> None:
    """Store a fact or preference in semantic memory."""
    from guardian.memory import get_memory_manager
    mm = get_memory_manager()
    if "=" not in fact:
        console.print('[red]Error:[/red] Fact must be in "key=value" format')
        raise typer.Exit(code=1)
    key, _, value = fact.partition("=")
    try:
        mm.semantic.set(key.strip(), value.strip(), category=category)
        console.print(f"[green]Remembered:[/green] {key.strip()!r} = {value.strip()!r} [{category}]")
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)


@memory_app.command("search")
def memory_search(
    query: str = typer.Argument(help="Search term"),
    limit: int = typer.Option(10, "--limit", "-n"),
) -> None:
    """Search episodic memory by keyword."""
    from guardian.memory import get_memory_manager
    mm = get_memory_manager()
    results = mm.episodic.search(query, limit=limit)
    if not results:
        console.print(f"[dim]No results for {query!r}[/dim]")
        return
    console.print(f"[dim]{len(results)} result(s) for {query!r}:[/dim]\n")
    for r in results:
        console.print(Panel(
            f"[bold]You:[/bold] {r.user_message}\n\n[bold]Guardian:[/bold] {r.assistant_reply[:300]}",
            title=f"[dim]{r.timestamp.strftime('%Y-%m-%d %H:%M')} | {r.model_name}[/dim]",
            title_align="left",
            border_style="dim",
        ))


@memory_app.command("forget")
def memory_forget(
    record_id: str = typer.Argument(help="Record ID (or first 8 chars) to delete"),
) -> None:
    """Permanently delete a specific memory record."""
    from guardian.memory import get_memory_manager
    mm = get_memory_manager()

    # Support short IDs: find full ID if partial match
    if len(record_id) < 36:
        all_records = mm.episodic.list_recent(1000)
        matches = [r for r in all_records if r.id.startswith(record_id)]
        if not matches:
            console.print(f"[red]Not found:[/red] no record starting with {record_id!r}")
            raise typer.Exit(code=1)
        if len(matches) > 1:
            console.print(f"[red]Ambiguous:[/red] {len(matches)} records match. Use more characters.")
            raise typer.Exit(code=1)
        record_id = matches[0].id

    if mm.episodic.delete(record_id):
        console.print(f"[green]Deleted:[/green] {record_id[:8]}...")
    else:
        console.print(f"[yellow]Not found:[/yellow] {record_id}")


@memory_app.command("clear")
def memory_clear(
    facts: bool = typer.Option(False, "--facts", "-f", help="Clear semantic facts instead"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Delete all memory records (irreversible)."""
    from guardian.memory import get_memory_manager
    mm = get_memory_manager()

    target = "semantic facts" if facts else "episodic records"
    count = mm.semantic.count() if facts else mm.episodic.count()

    if count == 0:
        console.print(f"[dim]No {target} to delete.[/dim]")
        return

    if not yes:
        confirm = console.input(f"Delete all {count} {target}? [y/N] ").strip().lower()
        if confirm != "y":
            console.print("[dim]Cancelled.[/dim]")
            return

    if facts:
        deleted = mm.semantic.clear()
    else:
        deleted = mm.episodic.clear()

    console.print(f"[green]Cleared:[/green] {deleted} {target} deleted.")




# ─── Tools commands ───────────────────────────────────────────────────────────

@tools_app.command("list")
def tools_list() -> None:
    """List all available Guardian tools with their authority levels."""
    from guardian.tools import get_tool_executor
    exe = get_tool_executor()
    tools = exe.list_tools()

    console.print()
    level_colors = {0: "green", 1: "yellow", 2: "red"}
    level_labels = {0: "L0-READ", 1: "L1-WRITE", 2: "L2-DANGER"}

    t = Table(title="[bold]Guardian Tools[/bold]", box=box.SIMPLE)
    t.add_column("Name", style="cyan", width=14)
    t.add_column("Level", width=12)
    t.add_column("Description")

    for tool in sorted(tools, key=lambda x: (x.level, x.name)):
        lvl = tool.level
        color = level_colors.get(lvl, "white")
        label = level_labels.get(lvl, str(lvl))
        t.add_row(tool.name, f"[{color}]{label}[/{color}]", tool.description)

    console.print(t)
    console.print(
        "[dim]L0=no approval  L1=approved=True  L2=user confirmation always required[/dim]\n"
        "[dim]In chat: /read <path>  /ls [path]  /search <term>  /run <cmd>[/dim]"
    )
    console.print()

# -- Skills commands --

@skills_app.command("list")
def skills_list() -> None:
    """List all available Guardian skill modes."""
    from guardian.skills import get_skill_registry
    registry = get_skill_registry()

    console.print()
    t = Table(title="[bold]Guardian Skills[/bold]", box=box.SIMPLE)
    t.add_column("Icon", width=5)
    t.add_column("Name", style="cyan", width=12)
    t.add_column("Title", width=14)
    t.add_column("Description")
    t.add_column("Keywords (sample)", style="dim")

    for skill in registry.list_all():
        sample_kw = ", ".join(skill.keywords[:4]) + ("..." if len(skill.keywords) > 4 else "")
        t.add_row(
            skill.icon,
            skill.name,
            skill.title,
            skill.description,
            sample_kw,
        )

    console.print(t)
    console.print(
        "[dim]Skills are auto-detected from your message in 'guardian chat'.\n"
        "Force a skill with: /skill <name>[/dim]"
    )
    console.print()


# ─── Security commands ────────────────────────────────────────────────────────

@security_app.command("audit")
def security_audit(
    persist: bool = typer.Option(True, "--persist/--no-persist", help="Save findings to threat DB"),
) -> None:
    """Run self-audit: check Guardian config, secrets hygiene, .gitignore."""
    from guardian.security import get_security_guardian, reset_security_guardian
    reset_security_guardian()
    sg = get_security_guardian()
    console.print("\n[bold]Running self-audit...[/bold]")
    with console.status("[dim]Scanning...[/dim]", spinner="dots"):
        findings = sg.run_audit(persist=persist)
    _print_findings(findings, "Self-Audit")


@security_app.command("scan")
def security_scan(
    persist: bool = typer.Option(True, "--persist/--no-persist", help="Save findings to threat DB"),
) -> None:
    """Scan local environment: processes, ports, sensitive files."""
    from guardian.security import get_security_guardian, reset_security_guardian
    reset_security_guardian()
    sg = get_security_guardian()
    console.print("\n[bold]Scanning environment...[/bold]")
    console.print("[dim](Port scan may take up to 15s)[/dim]")
    with console.status("[dim]Scanning...[/dim]", spinner="dots"):
        findings = sg.run_scan(persist=persist)
    _print_findings(findings, "Environment Scan")


@security_app.command("threats")
def security_threats(
    all_threats: bool = typer.Option(False, "--all", "-a", help="Include acknowledged findings"),
    min_severity: str = typer.Option("info", "--min", help="Minimum severity: info/low/medium/high/critical"),
) -> None:
    """Show stored threat findings from previous scans."""
    from guardian.security import get_security_guardian, reset_security_guardian
    from guardian.security.threat import Severity
    reset_security_guardian()
    sg = get_security_guardian()
    try:
        min_sev = Severity(min_severity.lower())
    except ValueError:
        console.print(f"[red]Invalid severity: {min_severity!r}. Use: info/low/medium/high/critical[/red]")
        raise typer.Exit(1)
    findings = sg.store.list_all() if all_threats else sg.store.list_active(min_severity=min_sev)
    _print_findings(findings, "Stored Threats", show_ack=all_threats)


@security_app.command("report")
def security_report(
    output: str = typer.Option("", "--output", "-o", help="Write report to file (optional)"),
) -> None:
    """Generate a full security report from stored findings."""
    from guardian.security import get_security_guardian, reset_security_guardian
    reset_security_guardian()
    sg = get_security_guardian()
    report_text = sg.report(include_acknowledged=True)
    console.print(report_text)
    if output:
        from pathlib import Path
        Path(output).write_text(report_text, encoding="utf-8")
        console.print(f"\n[dim]Report written to: {output}[/dim]")


@security_app.command("analyze")
@security_app.command("social-engineering")
def security_social_engineering(
    target: str = typer.Argument(..., help="Text content or path to file/email to analyze"),
) -> None:
    """Analyze communications for social engineering, spear-phishing, and SET attack vectors."""
    from pathlib import Path
    from guardian.security.social_engineering import get_social_engineering_detector, RiskTier

    content = target
    p = Path(target)
    if p.exists() and p.is_file():
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            console.print(f"[dim]Loaded target file: {target} ({len(content)} chars)[/dim]")
        except Exception as e:
            console.print(f"[red]Error reading file {target}:[/red] {e}")
            raise typer.Exit(1)

    detector = get_social_engineering_detector()
    report = detector.analyze(content)

    tier_styles = {
        RiskTier.SAFE: "green",
        RiskTier.LOW: "cyan",
        RiskTier.MEDIUM: "yellow",
        RiskTier.HIGH: "red",
        RiskTier.CRITICAL: "bold white on red",
    }
    style = tier_styles.get(report.risk_tier, "white")

    console.print()
    console.print(Panel(
        f"[bold]Risk Tier:[/bold] [{style}] {report.risk_tier.value} [/{style}]   "
        f"[bold]Risk Score:[/bold] {report.risk_score:.2f} / 1.00\n"
        f"[bold]SET Vectors:[/bold] {', '.join(report.detected_vectors) or 'None'}\n"
        f"[bold]Psychological Triggers:[/bold] {', '.join(report.psychological_triggers) or 'None'}",
        title="[bold red]SOCIAL ENGINEERING DEFENSE REPORT[/bold red]",
        border_style="red" if report.is_malicious else "green",
        box=box.ROUNDED,
    ))

    if report.indicators:
        t = Table(title="[bold]Detected Threat Indicators[/bold]", box=box.SIMPLE)
        t.add_column("Category", style="cyan", width=22)
        t.add_column("Vector", style="dim", width=24)
        t.add_column("Description")
        t.add_column("Sev", width=6)
        for ind in report.indicators:
            t.add_row(ind.category, ind.vector, ind.description, f"{ind.severity:.2f}")
        console.print(t)

    if report.urls_analyzed:
        t_url = Table(title="[bold]URL Intelligence[/bold]", box=box.SIMPLE)
        t_url.add_column("URL", style="dim")
        t_url.add_column("Status", width=12)
        t_url.add_column("Details")
        for u in report.urls_analyzed:
            status = "[red]SUSPICIOUS[/red]" if u["is_suspicious"] else "[green]BENIGN[/green]"
            t_url.add_row(u["url"][:50], status, u["reason"])
        console.print(t_url)

    console.print("\n[bold]Defensive Recommendations:[/bold]")
    for r in report.recommendations:
        console.print(f"  • {r}")
    console.print()


# ─── Canary & Honeypot commands ───────────────────────────────────────────────

@canary_app.command("plant")
def canary_plant(
    name: str = typer.Argument(..., help="Name of the canary token / decoy"),
    token_type: str = typer.Option("honey_file", "--type", "-t", help="Canary type: honey_file or decoy_secret"),
    path: str = typer.Option("", "--path", "-p", help="Relative file path for honey_file"),
) -> None:
    """Plant an autonomous canary token or honey-file lure."""
    from guardian.security.canary import get_canary_manager, CanaryType
    mgr = get_canary_manager()
    if token_type == CanaryType.DECOY_SECRET.value:
        token = mgr.plant_decoy_secret(name)
        console.print(f"[green]Planted Decoy Secret:[/green] {token.name} (ID: {token.id})")
        console.print(f"Decoy Token Value: [cyan]{token.value}[/cyan]")
    else:
        token = mgr.plant_honey_file(name, relative_path=path or None)
        console.print(f"[green]Planted Honey-File:[/green] {token.name} (ID: {token.id})")
        console.print(f"Location: [cyan]{token.file_path}[/cyan]")
    console.print("[dim]Canary is armed and actively monitored.[/dim]\n")


@canary_app.command("list")
def canary_list() -> None:
    """List all planted canary tokens and honeypots."""
    from guardian.security.canary import get_canary_manager
    mgr = get_canary_manager()
    tokens = mgr.list_tokens()
    if not tokens:
        console.print("[dim]No canary tokens planted. Use 'guardian security canary plant' to create one.[/dim]")
        return

    t = Table(title="[bold]Autonomous Canary Tokens & Honeypots[/bold]", box=box.SIMPLE)
    t.add_column("ID", style="dim", width=12)
    t.add_column("Name", width=22)
    t.add_column("Type", width=16)
    t.add_column("Status", width=12)
    t.add_column("Details")

    for tok in tokens:
        status = "[bold red]TRIPPED[/bold red]" if tok.triggered else "[green]ARMED[/green]"
        details = tok.file_path if tok.file_path else tok.value[:28] + "..."
        t.add_row(tok.id, tok.name, tok.token_type, status, details)
    console.print(t)


@canary_app.command("check")
def canary_check() -> None:
    """Verify integrity of all honey-files; detect tampering or deletion."""
    from guardian.security.canary import get_canary_manager
    mgr = get_canary_manager()
    alerts = mgr.check_integrity()
    if not alerts:
        console.print("[green]Integrity Check Passed:[/green] All planted honey-files are intact and untampered.")
    else:
        console.print(f"[bold red]SECURITY INTRUSION DETECTED![/bold red] {len(alerts)} alerts triggered:")
        for a in alerts:
            console.print(f"  • [{a['status']}] {a['name']}: {a['reason']}")


@canary_app.command("remove")
def canary_remove(
    token_id: str = typer.Argument(..., help="ID of token to remove"),
) -> None:
    """Remove a canary token and clean up its file."""
    from guardian.security.canary import get_canary_manager
    mgr = get_canary_manager()
    if mgr.remove_token(token_id):
        console.print(f"[green]Removed canary token:[/green] {token_id}")
    else:
        console.print(f"[red]Token not found:[/red] {token_id}")


def _print_findings(findings, scan_type: str, show_ack: bool = False) -> None:
    """Shared helper to display findings in a table."""
    active = [f for f in findings if not f.acknowledged]
    acked  = [f for f in findings if f.acknowledged]

    console.print()
    if not findings:
        console.print(f"[green]{scan_type}: No findings.[/green]")
        console.print()
        return

    console.print(f"[bold]{scan_type}:[/bold] {len(active)} active, {len(acked)} acknowledged\n")
    t = Table(box=box.SIMPLE)
    t.add_column("Sev", width=9)
    t.add_column("Category", width=12)
    t.add_column("Title")

    sev_styles = {
        "info": "dim", "low": "cyan", "medium": "yellow",
        "high": "red", "critical": "bold red",
    }

    shown = findings if show_ack else active
    for f in sorted(shown, key=lambda x: -x.severity.rank):
        style = sev_styles.get(f.severity.value, "white")
        ack_mark = " [ack]" if f.acknowledged else ""
        t.add_row(
            f"[{style}]{f.severity.value.upper()}[/{style}]",
            f.category.value,
            f.title + ack_mark,
        )
    console.print(t)
    console.print("[dim]Use 'guardian security report' for full details.[/dim]")
    console.print()


# ─── Knowledge commands ───────────────────────────────────────────────────────

def _get_kl():
    """Lazily import and return the KnowledgeLayer singleton."""
    import os
    os.environ["PYTHONNOUSERSITE"] = "1"
    from guardian.knowledge import get_knowledge_layer, reset_knowledge_layer
    reset_knowledge_layer()
    return get_knowledge_layer()


@knowledge_app.command("ingest")
def knowledge_ingest(
    path: str = typer.Argument(..., help="File or directory to ingest"),
    replace: bool = typer.Option(True, "--replace/--no-replace",
                                 help="Replace existing chunks for this source"),
) -> None:
    """Ingest a file or directory into the Guardian knowledge base."""
    from pathlib import Path
    kl   = _get_kl()
    p    = Path(path)
    console.print(f"\n[bold]Ingesting:[/bold] {path}")
    with console.status("[dim]Loading and embedding...[/dim]", spinner="dots"):
        result = kl.ingest(p, replace=replace)
    if result.success:
        console.print(
            f"[green]OK[/green]  {result.chunks_added} chunk(s) added "
            f"from {result.chars_loaded:,} chars"
        )
    elif result.skipped:
        console.print(f"[yellow]Skipped:[/yellow] {result.source} "
                      f"(unsupported or empty)")
    else:
        console.print(f"[red]Error:[/red] {result.error}")
    console.print()


@knowledge_app.command("query")
def knowledge_query(
    question: str = typer.Argument(..., help="Question or search text"),
    n: int = typer.Option(5, "--n", "-n", help="Max results"),
    verbose: bool = typer.Option(False, "--verbose", "-v",
                                 help="Show full chunk content"),
) -> None:
    """Search the knowledge base and show relevant document chunks."""
    kl = _get_kl()
    if kl.is_empty():
        console.print("\n[yellow]Knowledge base is empty.[/yellow] "
                      "Run: guardian knowledge ingest <path>\n")
        raise typer.Exit(0)

    with console.status("[dim]Searching...[/dim]", spinner="dots"):
        result = kl.query(question, n_results=n)

    console.print()
    if not result.found:
        console.print("[yellow]No relevant results found.[/yellow]")
        console.print()
        return

    console.print(f"[bold]Results for:[/bold] {question!r}  "
                  f"[dim]({len(result.hits)} hit(s))[/dim]\n")
    for i, hit in enumerate(result.hits, 1):
        console.print(
            f"[bold cyan]{i}.[/bold cyan] [dim]{hit.source} "
            f"(chunk {hit.chunk_index + 1})[/dim]  "
            f"relevance: [bold]{hit.relevance:.3f}[/bold]"
        )
        snippet = hit.content[:300 if not verbose else 2000].strip()
        if len(hit.content) > 300 and not verbose:
            snippet += "..."
        console.print(f"   {snippet}\n")
    console.print("[dim]Add --verbose to see full chunks.[/dim]\n")


@knowledge_app.command("list")
def knowledge_list() -> None:
    """List all ingested document sources in the knowledge base."""
    kl = _get_kl()
    sources = kl.list_sources()
    status  = kl.status()

    console.print()
    console.print(f"[bold]Knowledge Base[/bold]  "
                  f"[dim]{status['total_chunks']} chunk(s) total[/dim]")
    console.print()
    if not sources:
        console.print("[yellow]Empty — no documents ingested yet.[/yellow]")
    else:
        for src in sources:
            console.print(f"  [cyan]•[/cyan] {src}")
    console.print()


@knowledge_app.command("forget")
def knowledge_forget(
    source: str = typer.Argument(..., help="Source path to remove (from 'guardian knowledge list')"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Remove all chunks from a specific source document."""
    if not yes:
        confirmed = typer.confirm(f"Delete all chunks from {source!r}?")
        if not confirmed:
            console.print("[dim]Aborted.[/dim]")
            raise typer.Exit(0)
    kl      = _get_kl()
    deleted = kl.delete_source(source)
    if deleted > 0:
        console.print(f"[green]Deleted {deleted} chunk(s) from {source!r}[/green]")
    else:
        console.print(f"[yellow]No chunks found for {source!r}[/yellow]")
    console.print()


@knowledge_app.command("status")
def knowledge_status() -> None:
    """Show knowledge base statistics."""
    kl     = _get_kl()
    status = kl.status()
    console.print()
    console.print(Panel(
        f"[bold]Total chunks:[/bold]  {status['total_chunks']}\n"
        f"[bold]Embedder:[/bold]     {status['embedder']}\n"
        f"[bold]Sources:[/bold]      {len(status['sources'])} document(s)",
        title="Knowledge Base", expand=False,
    ))
    console.print()


# ─── MCP commands ─────────────────────────────────────────────────────────────

@mcp_app.command("serve")
def mcp_serve() -> None:
    """
    Start the Guardian MCP server (stdio transport).

    External MCP clients (Claude Desktop, Open WebUI, Cursor) connect to this.
    The server exposes: file_read, directory, search, knowledge_query,
    security_audit.

    Typically launched via MCP client config, not manually.
    """
    from guardian.mcp.server import run_server
    console.print("[dim]Guardian MCP server starting (stdio)...[/dim]")
    run_server()


# ─── Guardrails commands ──────────────────────────────────────────────────────

@guardrails_app.command("scan")
def guardrails_scan(
    text: str = typer.Argument(..., help="Text to scan for threats"),
    direction: str = typer.Option("both", "--direction", "-d",
                                  help="Scan direction: input | output | both"),
) -> None:
    """Scan text for prompt injection, PII, secrets, and other threats."""
    from guardian.guardrails import make_test_layer
    layer = make_test_layer()
    console.print()

    result = layer.quick_scan(text)

    if result["passed"]:
        console.print("[bold green]PASS[/bold green]  No threats detected.")
    else:
        score = result["risk_score"]
        console.print(f"[bold red]BLOCK[/bold red]  risk_score={score:.2f}")

    if result["violations"]:
        console.print()
        from rich import box as _box
        from rich.table import Table
        t = Table(box=_box.SIMPLE, show_header=True, header_style="bold")
        t.add_column("Category", style="cyan")
        t.add_column("Severity")
        t.add_column("Match (truncated)", style="dim")
        for v in result["violations"]:
            sev = v["severity"]
            sev_color = {"critical": "red", "high": "yellow",
                         "medium": "blue", "low": "white"}.get(sev, "white")
            t.add_row(
                v["category"],
                f"[{sev_color}]{sev}[/{sev_color}]",
                v["match"][:50],
            )
        console.print(t)

    if result["sanitised"] != text:
        console.print("[dim]Sanitised output:[/dim]")
        console.print(result["sanitised"][:300])
    console.print()


@guardrails_app.command("status")
def guardrails_status() -> None:
    """Show active guardrails configuration and pattern counts."""
    from guardian.guardrails import get_guardrails_layer
    layer = get_guardrails_layer()
    s = layer.status()

    console.print()
    console.print(Panel(
        f"[bold]Rails active:[/bold]     {s.rails_count}\n"
        f"[bold]Pattern groups:[/bold]   {', '.join(s.pattern_groups)}\n"
        f"[bold]Total patterns:[/bold]   {s.pattern_total}\n"
        f"[bold]Block severities:[/bold] {', '.join(sorted(s.input_block_severities))}\n"
        f"[bold]Output redact PII:[/bold] {'yes' if s.output_redact_pii else 'no'}\n"
        f"[bold]Audit to ThreatDB:[/bold] {'yes' if s.audit_enabled else 'no'}",
        title="Guardian Guardrails",
        expand=False,
    ))
    console.print()


# ─── Models catalog & intelligent routing (Sections 3, 4, 5) ─────────────────

@models_app.command("catalog")
def models_catalog(
    modality: str = typer.Option("", "--modality", "-m", help="Filter by modality: text, vision, audio, code, multimodal"),
    tag: str = typer.Option("", "--tag", "-t", help="Filter by capability tag"),
    deployment: str = typer.Option("", "--deployment", "-d", help="Filter by deployment: api, local, both"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full model metadata"),
) -> None:
    """List all 20 candidate models from the Section 4 Model Catalog."""
    from guardian.model.catalog import get_candidate_catalog
    catalog = get_candidate_catalog()
    entries = catalog.filter(
        modality=modality or None,
        tag=tag or None,
        deployment=deployment or None,
    )
    t = Table(
        title=f"[bold]Guardian Model Catalog — Section 4[/bold] ({len(entries)} models)",
        box=box.SIMPLE,
    )
    t.add_column("#", style="dim", width=3)
    t.add_column("Model ID", style="cyan")
    t.add_column("Provider")
    t.add_column("Modality")
    t.add_column("Deploy")
    t.add_column("OK?")
    if verbose:
        t.add_column("Tags")
    for i, e in enumerate(entries, 1):
        d = e.to_dict()
        elig = catalog.verify_candidate_eligibility(e.model_id)
        ok = "[green]YES[/green]" if elig["eligible"] else "[red]NO[/red]"
        row = [str(i), d.get("model_id", ""), d.get("provider", ""),
               d.get("modality", ""), d.get("deployment", ""), ok]
        if verbose:
            row.append(", ".join(d.get("tags", [])))
        t.add_row(*row)
    console.print()
    console.print(t)
    console.print(f"\n[dim]Guardian Master System Prompt v1.0 — Section 4: Initial Model Catalog[/dim]\n")


@models_app.command("route")
def models_route(
    query: str = typer.Argument(..., help="Task query to classify and route"),
    has_images: bool = typer.Option(False, "--images", help="Query includes image input"),
    has_audio: bool = typer.Option(False, "--audio", help="Query includes audio input"),
    has_pdf: bool = typer.Option(False, "--pdf", help="Query includes PDF input"),
    require_local: bool = typer.Option(False, "--local", help="Force local-only model selection"),
) -> None:
    """Classify a query and select the minimal suitable model/tool set — Section 5."""
    from guardian.model.task_router import get_task_router
    router = get_task_router()
    decision = router.route_request(
        query=query,
        has_images=has_images,
        has_audio=has_audio,
        has_pdf=has_pdf,
        require_local=require_local,
    )
    d = decision.to_dict()
    console.print()
    t = Table(title="[bold]Intelligent Task Router — Section 5[/bold]", box=box.SIMPLE, show_header=False)
    t.add_column("Field", style="cyan", width=24)
    t.add_column("Value")
    t.add_row("Task Type", str(d.get("task_type", "")))
    t.add_row("Selected Model / Tool", str(d.get("selected_model_or_tool", "")))
    t.add_row("Selection Reason", str(d.get("selection_reason", "")))
    t.add_row("Input Modalities", ", ".join(d.get("input_modalities", [])))
    t.add_row("Output Modalities", ", ".join(d.get("output_modalities", [])))
    collabs = [f"{c.get('role', '')}: {c.get('model', '')}" for c in d.get("collaborators", [])]
    t.add_row("Collaborators (Sec 6)", ", ".join(collabs) or "None (single model sufficient)")
    t.add_row("External Evidence", str(d.get("requires_external_evidence", False)))
    t.add_row("Local Retrieval", str(d.get("requires_local_retrieval", False)))
    console.print(t)
    console.print()
    console.print(Panel(decision.format_routing_report(), title="[dim]Routing Report (Section 17)[/dim]",
        border_style="dim", expand=False))
    console.print()


@models_app.command("slots")
def models_slots() -> None:
    """Layer 1: List the Twenty-Slot Model Foundation matrix (Architecture 2.0)."""
    from guardian.model.slots import get_slot_registry
    registry = get_slot_registry()
    dash = registry.get_status_dashboard()

    t = Table(title=f"[bold]Twenty-Slot Model Foundation[/bold] (Active: {dash['loaded_count']}/{dash['policy']['max_parallel_models']} max parallel)", box=box.SIMPLE)
    t.add_column("Slot", style="dim", width=4)
    t.add_column("ID", style="cyan")
    t.add_column("Repo")
    t.add_column("Task")
    t.add_column("Adapter")
    t.add_column("RAM/VRAM", style="dim")
    t.add_column("State")
    t.add_column("Loaded?")

    for s in dash["slots"]:
        state_style = "green" if s["state"] == "healthy" else ("blue" if s["state"] == "loaded" else ("red" if s["state"] == "failed" else "dim"))
        loaded_str = "[bold green]YES (RAM)[/bold green]" if s["is_loaded"] else "[dim]NO[/dim]"
        mem_str = f"{s['estimated_ram_gb']:.0f}G/{s['estimated_vram_gb']:.0f}G"
        t.add_row(
            f"{s['slot_number']:02d}",
            s["id"],
            s["repo"],
            s["task"],
            s["adapter_name"],
            mem_str,
            f"[{state_style}]{s['state'].upper()}[/{state_style}]",
            loaded_str,
        )
    console.print()
    console.print(t)
    console.print(f"[dim]Policy: load_on_demand=true, max_parallel_models={dash['policy']['max_parallel_models']}[/dim]\n")


@models_app.command("verify")
def models_verify(
    slot: Optional[int] = typer.Argument(None, help="Slot number (1-20) to verify, or omit to verify all"),
) -> None:
    """Verify repository existence, hardware requirements, and adapter health."""
    from guardian.model.slots import get_slot_registry
    registry = get_slot_registry()
    console.print()
    if slot is not None:
        res = registry.verify_slot(slot)
        st_color = "green" if res["verified"] else "red"
        console.print(f"Slot {slot:02d} (`{res['id']}`): [{st_color}]{res['state'].upper()}[/{st_color}]")
        for n in res.get("notes", []):
            console.print(f"  • {n}")
    else:
        results = registry.verify_all_slots()
        t = Table(title="[bold]Verification of All 20 Model Slots[/bold]", box=box.SIMPLE)
        t.add_column("Slot", width=4)
        t.add_column("ID", style="cyan")
        t.add_column("Status")
        for num, res in results.items():
            st_color = "green" if res["verified"] else "red"
            t.add_row(f"{num:02d}", res["id"], f"[{st_color}]{res['state'].upper()}[/{st_color}]")
        console.print(t)
    console.print()


@models_app.command("load")
def models_load(
    slot: int = typer.Argument(..., help="Slot number (1-20) to load into active memory"),
) -> None:
    """Load model slot into memory on demand (enforces max 2 parallel models)."""
    from guardian.model.slots import get_slot_registry
    registry = get_slot_registry()
    res = registry.load_slot(slot)
    if res.get("success"):
        console.print(f"\n[bold green]Loaded Slot {slot:02d} (`{res.get('id')}`)[/bold green]")
        if res.get("evicted_slot"):
            console.print(f"[yellow]LRU eviction: Evicted Slot {res['evicted_slot']:02d} to enforce max {registry.policy.max_parallel_models} models.[/yellow]")
        console.print(f"[dim]Currently loaded slots: {res.get('currently_loaded')}[/dim]\n")
    else:
        console.print(f"\n[red]Failed to load slot {slot}:[/red] {res.get('error')}\n")


@models_app.command("run")
def models_run(
    slot: int = typer.Argument(..., help="Slot number (1-20) to execute"),
    prompt: str = typer.Argument(..., help="Task prompt or query"),
) -> None:
    """Run a task prompt on a specific model slot adapter."""
    from guardian.model.slots import get_slot_registry
    registry = get_slot_registry()
    with console.status(f"[dim]Running slot {slot}...[/dim]"):
        res = registry.run_task(slot, {"prompt": prompt, "query": prompt})
    console.print()
    t = Table(title=f"[bold]Execution Result — Slot {slot:02d}[/bold]", box=box.SIMPLE, show_header=False)
    t.add_column("Field", style="cyan", width=16)
    t.add_column("Value")
    t.add_row("Status", res.status.upper())
    t.add_row("Slot ID", res.slot_id)
    t.add_row("Output", str(res.output)[:400])
    if res.error:
        t.add_row("Error", res.error)
    console.print(t)
    console.print()


# ─── Digital Access Gateway CLI Commands (Layer 3) ────────────────────────────

@web_app.command("search")
def web_search_cmd(
    query: str = typer.Argument(..., help="Search query string"),
    max_results: int = typer.Option(5, "--limit", "-n", help="Maximum results to return"),
) -> None:
    """Layer 3: Search the public web with SSRF validation."""
    from guardian.web.gateway import get_digital_access_gateway
    gw = get_digital_access_gateway()
    results = gw.search_web(query, max_results=max_results)
    console.print()
    t = Table(title=f"[bold]Web Search Results: '{query}'[/bold]", box=box.SIMPLE)
    t.add_column("#", width=3)
    t.add_column("Title", style="cyan")
    t.add_column("URL", style="dim")
    for i, r in enumerate(results, 1):
        t.add_row(str(i), r.title[:45], r.url[:60])
    console.print(t)
    console.print()


@web_app.command("fetch")
def web_fetch_cmd(
    url: str = typer.Argument(..., help="Target URL to fetch and sanitize"),
) -> None:
    """Layer 3: Safe web page retrieval with SSRF defense and untrusted content wrapping."""
    from guardian.web.gateway import get_digital_access_gateway
    gw = get_digital_access_gateway()
    with console.status("[dim]Fetching page with SSRF check...[/dim]"):
        page = gw.fetch_page(url)
    console.print()
    if page.success:
        from rich.markup import escape
        console.print(f"[bold green]Fetched Successfully ({page.status_code})[/bold green]: {page.title or url}")
        preview = page.text[:500] + ("..." if len(page.text) > 500 else "")
        console.print(Panel(escape(preview), title="[dim]Sanitized Content Preview[/dim]", border_style="dim"))
    else:
        console.print(f"[bold red]Fetch Blocked/Failed:[/bold red] {page.error}")
    console.print()


# ─── Permission & Safety Gateway CLI Commands (Layer 4) ───────────────────────

@permissions_app.command("status")
def permissions_status_cmd() -> None:
    """Layer 4: Display operational permission tiers, confirmation gates, and kill switch."""
    from guardian.security.permissions import get_permission_gateway
    gw = get_permission_gateway()
    sec = gw.get_security_status()
    console.print()
    t = Table(title="[bold]Permission & Operational Safety Gateway (Section 9)[/bold]", box=box.SIMPLE, show_header=False)
    t.add_column("Field", style="cyan", width=24)
    t.add_column("Value")
    t.add_row("Emergency Kill Switch", "[red]ACTIVE (HALTED)[/red]" if sec["kill_switch_active"] else "[green]DISARMED (NORMAL)[/green]")
    t.add_row("Require Approval", str(sec["require_approval"]))
    t.add_row("Pending Proposals", str(len(sec["pending_proposals"])))
    t.add_row("Recent Audit Records", str(sec["recent_audit_records"]))
    for lvl in sec["permission_levels"]:
        t.add_row("Permission Level", lvl)
    console.print(t)
    console.print()


# ─── Voice commands ────────────────────────────────────────────────────────────

@voice_app.command("say")
def voice_say(
    text: str = typer.Argument(..., help="Text to speak"),
    voice: str = typer.Option("en-US-AriaNeural", "--voice", "-v",
                              help="Voice name (EdgeTTS) or piper model path"),
) -> None:
    """Synthesize speech and play through speakers."""
    from guardian.voice.tts import EdgeTTSSynthesizer
    tts = EdgeTTSSynthesizer(voice=voice)
    from guardian.voice import VoiceLayer
    from guardian.voice.stt import MockTranscriber
    from guardian.voice.wake import MockWakeWordDetector
    vl = VoiceLayer(MockTranscriber(), tts, MockWakeWordDetector())
    console.print(f"\n[dim]Speaking ({voice})...[/dim]")
    try:
        result = vl.say(text, blocking=True)
        console.print(f"[dim]Done ({result.duration_s:.2f}s)[/dim]\n")
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")
        console.print("[dim]Tip: ensure internet access for EdgeTTS, or set GUARDIAN_PIPER_PATH.[/dim]\n")


@voice_app.command("start")
def voice_assistant(
    model: str = typer.Option("base", "--model", "-m", help="Whisper model: tiny/base/small/medium/large-v3"),
    llm: str = typer.Option("", "--llm", "-l", help="LLM Backend: groq, gemini, mock"),
) -> None:
    """Start the Continuous Voice Assistant Loop with 3D UI."""
    from guardian.voice import get_voice_layer
    from guardian.core.orchestrator import GuardianCore
    from guardian.core.session import Session
    from guardian.memory import get_memory_manager
    from guardian.model.registry import get_model
    from guardian.prompts import GUARDIAN_MASTER_SYSTEM_PROMPT_V1
    from guardian.skills import GUARDIAN_SKILL
    
    # 1. Start the Presence WebSocket server in a background thread
    import threading
    from guardian.core.presence_server import start_server, broadcaster
    server_thread = threading.Thread(target=start_server, kwargs={"host": "127.0.0.1", "port": 8000}, daemon=True)
    server_thread.start()
    
    # 2. Init AI Core
    console.print("[dim]Initializing AI Core...[/dim]")
    backend = get_model(prefer=llm if llm else None)
    try:
        mm = get_memory_manager()
        system_prompt = mm.build_system_prompt(GUARDIAN_MASTER_SYSTEM_PROMPT_V1)
    except Exception:
        system_prompt = GUARDIAN_MASTER_SYSTEM_PROMPT_V1
        
    # Voice-specific prompt: short, spoken-language responses only
    VOICE_PROMPT_ADDITION = (
        "\n\nIMPORTANT — Voice mode: Keep ALL responses under 3 sentences. "
        "No markdown, no bullet points, no lists. Speak naturally and concisely. "
        "Avoid filler phrases like 'Certainly!' or 'Of course!'. Get straight to the point."
    )
    system_prompt = system_prompt + VOICE_PROMPT_ADDITION
    core = GuardianCore(model=backend, system_prompt=system_prompt, max_tokens=300)
    session = Session()

    # 3. Init Voice Layer
    console.print("[dim]Initializing Voice I/O (STT + TTS + Wake)...[/dim]")
    vl = get_voice_layer(stt_model=model)
    
    def on_command(command_text: str):
        # We are on the background wake thread and wake word was just detected + transcribed!
        console.print(f"\n[bold green]Wake word detected![/bold green]")
        
        # Notify the UI to switch state to processing
        broadcaster.broadcast_sync({"event": "processing"})
        
        if not command_text:
            # They said "Hey Guardian" but nothing else. We should ask how we can help.
            console.print("[dim](No command detected)[/dim]")
            vl.say("Yes, I am here. How can I help?", blocking=True)
            return
            
        console.print(f"[bold cyan]You:[/bold cyan] {command_text}")
        
        # Process through LLM
        response = core.process(
            command_text, session,
            active_skill=GUARDIAN_SKILL.name,
            skill_prompt_addition=GUARDIAN_SKILL.prompt_addition,
        )
        
        if response.success:
            console.print(f"[bold magenta]Guardian:[/bold magenta] {response.content}")
            # Speak the response (this broadcasts to UI and plays audio)
            vl.say(response.content, blocking=True)
        else:
            console.print(f"[red]Error:[/red] {response.error}")
            vl.say("I encountered an error processing that request.", blocking=True)
            
    # Start the continuous wake loop
    console.print()
    
    wake_words = ["hey guardian", "guardian", "ok guardian", "yes guardian"]
    
    console.print(Panel(
        "[bold cyan]Guardian Voice Assistant Active[/bold cyan]\n"
        f"Wake words: [bold yellow]{', '.join(wake_words)}[/bold yellow]\n"
        "Just say the wake word followed by your command! (e.g. 'Hey Guardian, what time is it?')\n"
        "Press Ctrl+C to exit.",
        box=box.DOUBLE, expand=False
    ))
    
    vl.start_vad_wake_loop(wake_words=wake_words, on_command=on_command)
    
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[dim]Shutting down voice assistant...[/dim]")
        vl.stop()
def voice_listen(
    model: str = typer.Option("base", "--model", "-m",
                              help="Whisper model: tiny/base/small/medium/large-v3"),
    language: str = typer.Option(None, "--language", "-l",
                                 help="Force language (e.g. 'en', 'fr')"),
    seconds: float = typer.Option(10.0, "--seconds", "-s",
                                  help="Max recording duration"),
) -> None:
    """Record from microphone and transcribe with Whisper."""
    try:
        from guardian.voice import VoiceLayer
        from guardian.voice.stt import WhisperTranscriber
        from guardian.voice.tts import MockSynthesizer
        from guardian.voice.wake import MockWakeWordDetector
        stt = WhisperTranscriber(model=model, device="auto", compute_type="int8")
        vl = VoiceLayer(stt, MockSynthesizer(), MockWakeWordDetector())
        console.print(f"\n[bold]Listening for up to {seconds:.0f}s...[/bold] (speak now, silence ends)")
        result = vl.listen_once(max_seconds=seconds, language=language)
        console.print()
        console.print(Panel(
            f"[bold]{result.text}[/bold]" if result.text else "[dim](silence)[/dim]",
            title=f"[dim]Transcript ? {result.language} ? {result.duration_s:.2f}s[/dim]",
            expand=False,
        ))
        console.print()
        vl.stop()
    except Exception as exc:
        console.print(f"[red]Error:[/red] {exc}")


@voice_app.command("status")
def voice_status() -> None:
    """Show Voice I/O configuration and available backends."""

    from guardian.voice.tts import EdgeTTSSynthesizer, PiperSynthesizer

    piper_bin = PiperSynthesizer._find_binary(None)
    edge_ok   = EdgeTTSSynthesizer().is_available

    console.print()
    console.print(Panel(
        f"[bold]STT:[/bold]      faster-whisper (MIT) ? models: tiny/base/small/medium/large-v3\n"
        f"[bold]TTS (primary):[/bold]  Piper (subprocess, GPL-3.0 isolated)\n"
        f"             binary: {piper_bin or '[yellow]not found[/yellow]'}\n"
        f"[bold]TTS (fallback):[/bold] Edge TTS (MIT, cloud) ? {'[green]available[/green]' if edge_ok else '[yellow]unavailable[/yellow]'}\n"
        f"[bold]Wake word:[/bold]  openWakeWord (Apache 2.0) ? hey_mycroft / alexa / hey_jarvis\n"
        f"[bold]Audio I/O:[/bold] sounddevice (MIT) + soundfile (BSD-3)\n"
        f"\n[dim]Set GUARDIAN_PIPER_PATH to point to your piper binary.\n"
        f"Download voices: https://huggingface.co/rhasspy/piper-voices[/dim]",
        title="Voice I/O",
        expand=False,
    ))
    console.print()

compliance_app = typer.Typer(help="Manage compliance references and view attestations.")
app.add_typer(compliance_app, name="compliance")

@compliance_app.command("list")
def list_compliance() -> None:
    """List all stored compliance references."""
    from guardian.policy.compliance import ComplianceStore
    from guardian.config.settings import settings
    
    store = ComplianceStore(settings.project_root / ".guardian" / "compliance.json")
    refs = store.get_all()
    
    if not refs:
        console.print("No compliance references found.")
        return
        
    t = Table(title="Compliance References")
    t.add_column("ID", style="cyan")
    t.add_column("Title")
    t.add_column("Last Verified")
    
    for r in refs:
        t.add_row(r.id, r.title, r.last_verified)
        
    console.print(t)

@app.command()
def risk(session_id: str = typer.Option("mock_session", help="Session ID to evaluate risk for")) -> None:
    """Display a combined view of EPSS, anomalies, and attack path predictions."""
    try:
        from guardian.core.agents import AnalysisAgent, ResponseAgent
        from guardian.security.scanner import EnvironmentScanner
        from guardian.config.settings import settings
        from rich.table import Table
        
        scanner = EnvironmentScanner(settings.project_root)
        findings = scanner.run()
        
        summary = AnalysisAgent.produce_summary(session_id, findings)
        
        suggestions = ResponseAgent.suggest_next_steps(["T1595"])
        
        t = Table(title=f"[bold red]Predictive Risk Summary (Session: {session_id})[/bold red]", show_lines=True)
        t.add_column("Category", style="cyan")
        t.add_column("Details")
        
        cves_str = "\n".join(f"{c['cve']} (EPSS: {c['epss']}): {c['title']}" for c in summary["high_priority_cves"]) or "None"
        t.add_row("High Priority CVEs (EPSS)", cves_str)
        
        anom_str = "\n".join(summary["anomalies"]) or "No anomalies detected."
        t.add_row("Anomaly Flags", anom_str)
        
        det_str = "\n".join(summary.get("detections", [])) or "No rule detections."
        t.add_row("Detection Rules", det_str)
        
        path_str = "\n".join(suggestions) or "No active predictions."
        t.add_row("Attack Path Prediction", path_str)
        
        console.print(t)
    except Exception as e:
        log.error(f"Risk command failed: {e}")
        console.print(f"[red]Error computing risk: {e}[/red]")
        raise typer.Exit(1)

# ── Gateway CLI Commands ───────────────────────────────────────────────────────

@gateway_app.command("start")
def gateway_start(
    bind_ip: Optional[str] = typer.Option(None, "--bind-ip", "-b", help="Specific IP to bind to (e.g. WireGuard IP)"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind to"),
    allow_insecure: bool = typer.Option(False, "--allow-insecure", help="Allow binding to 0.0.0.0 (testing only)"),
) -> None:
    """Start the Guardian Hub Remote Gateway (WireGuard/VPN-ready)."""
    try:
        from guardian.gateway.server import run_gateway
        from guardian.gateway.network import get_bind_address
        resolved_ip = get_bind_address(preferred_ip=bind_ip, allow_insecure=allow_insecure)
        console.print(f"[bold green]Starting Guardian Hub Gateway on {resolved_ip}:{port}[/bold green]")
        run_gateway(host=resolved_ip, port=port, allow_insecure=allow_insecure)
    except Exception as e:
        console.print(f"[bold red]Failed to start Gateway: {e}[/bold red]")
        raise typer.Exit(1)


@gateway_app.command("status")
def gateway_status() -> None:
    """Show gateway interface detection, bound addresses, and paired devices."""
    from rich.table import Table
    from guardian.gateway.network import find_wireguard_interfaces, get_bind_address
    from guardian.gateway.pairing import get_device_registry

    reg = get_device_registry()
    devices = reg.list_devices()
    pending = reg.list_pending()
    wg_ifaces = find_wireguard_interfaces()

    t = Table(title="[bold cyan]Guardian Hub Gateway Status[/bold cyan]")
    t.add_column("Property", style="bold")
    t.add_column("Value")

    default_bind = get_bind_address()
    t.add_row("Default Bind IP", f"[green]{default_bind}[/green]")
    t.add_row("Detected WireGuard Interfaces", str(len(wg_ifaces)))
    for iface in wg_ifaces:
        t.add_row(f"  Interface: {iface['name']}", f"IP: {iface['ip']} ({iface['detected_via']})")

    t.add_row("Paired Devices", str(len([d for d in devices if not d.is_revoked])))
    t.add_row("Pending Pairings", str(len(pending)))
    console.print(t)


@pair_app.command("list")
def pair_list() -> None:
    """List pending pairing requests and active paired devices."""
    from rich.table import Table
    from guardian.gateway.pairing import get_device_registry

    reg = get_device_registry()
    pending = reg.list_pending()
    devices = reg.list_devices()

    if pending:
        t_pend = Table(title="[bold yellow]Pending Device Pairings (Awaiting Approval)[/bold yellow]")
        t_pend.add_column("Request ID", style="cyan")
        t_pend.add_column("Pairing Code", style="bold green")
        t_pend.add_column("Device Name")
        t_pend.add_column("Approved?")
        t_pend.add_column("Expires In")

        now = time.time()
        for p in pending:
            exp = max(0, int(p.expires_at - now))
            approved_str = "[green]YES[/green]" if p.is_approved else "[yellow]NO (Needs Approval)[/yellow]"
            t_pend.add_row(p.request_id, p.pairing_code, p.device_name, approved_str, f"{exp}s")
        console.print(t_pend)
    else:
        console.print("[dim]No pending pairing requests.[/dim]")

    t_dev = Table(title="[bold cyan]Registered Paired Devices[/bold cyan]")
    t_dev.add_column("Device ID", style="cyan")
    t_dev.add_column("Name")
    t_dev.add_column("Paired At")
    t_dev.add_column("Last Seen")
    t_dev.add_column("Status")

    for d in devices:
        status_str = "[red]REVOKED[/red]" if d.is_revoked else "[green]ACTIVE[/green]"
        t_dev.add_row(d.device_id, d.device_name, d.paired_at, d.last_seen or "never", status_str)
    console.print(t_dev)


@pair_app.command("approve")
def pair_approve(
    code_or_id: str = typer.Argument(..., help="6-digit pairing code or request_id to approve"),
    operator: str = typer.Option("hub_operator", help="Operator identity for the audit log"),
) -> None:
    """Approve a pending device pairing request (creates cryptographic audit record)."""
    from guardian.gateway.pairing import get_device_registry

    reg = get_device_registry()
    approved = reg.approve_pairing(code_or_request_id=code_or_id, operator=operator)
    if not approved:
        console.print(f"[bold red]No pending pairing found matching '{code_or_id}' (or request expired).[/bold red]")
        raise typer.Exit(1)

    console.print(f"[bold green]Successfully approved pairing for device '{approved.device_name}'![/bold green]")
    console.print(f"Request ID: [cyan]{approved.request_id}[/cyan]")
    console.print(f"Audited operator: [dim]{operator}[/dim]")
    console.print("[dim]The client device can now finalize token issuance.[/dim]")


@pair_app.command("revoke")
def pair_revoke(
    device_id: str = typer.Argument(..., help="Device ID to revoke"),
    operator: str = typer.Option("hub_operator", help="Operator identity for the audit log"),
) -> None:
    """Revoke a paired device's access (audited event)."""
    from guardian.gateway.pairing import get_device_registry

    reg = get_device_registry()
    revoked = reg.revoke_device(device_id=device_id, operator=operator)
    if not revoked:
        console.print(f"[bold red]Device ID '{device_id}' not found or already revoked.[/bold red]")
        raise typer.Exit(1)

    console.print(f"[bold yellow]Device '{device_id}' has been revoked by {operator}.[/bold yellow]")


if __name__ == "__main__":
    app()
