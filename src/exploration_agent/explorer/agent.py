"""
Exploration Agent - Main Agent Loop

Architecture:
- Message queue: Agent sees full conversation history (its own reasoning)
- Each article/section gets its OWN message with unique ID
- Auto-delete: Temporary content deleted when agent takes non-save action
- Explicit save: Agent must use save_excerpt to keep information

Key flow:
1. Agent calls read_articles → We add N separate messages (one per article)
2. Agent calls save_excerpt → We save specified excerpts, keep temp content
3. Agent calls ANY other tool → We delete all temp content messages
"""

import json
import logging
from typing import Optional, List, Tuple, Dict, Any
from src.exploration_agent.models import (
    ExplorationMode,
    ExplorationState,
    ExplorationResult,
    TopicSnapshot,
    MessageEntry,
    SavedExcerpt,
)
from src.exploration_agent.explorer.tools import (
    get_topic_snapshot,
    get_initial_context,
    format_connected_topics,
    read_section,
    read_articles,
    ANALYSIS_SECTIONS,
)
from src.exploration_agent.explorer.prompt import EXPLORATION_SYSTEM_PROMPT
from src.llm.llm_router import get_llm
from src.llm.config import ModelTier
from utils import app_logging


def _quiet_third_party_logs() -> None:
    noisy_loggers = [
        "openai",
        "httpx",
        "httpcore",
        "httpcore.http11",
    ]
    for name in noisy_loggers:
        logging.getLogger(name).setLevel(logging.WARNING)


_quiet_third_party_logs()

# Use concise logger name to avoid overly long prefixes in output
logger = app_logging.get_logger("exploration_agent.explorer")


class ExplorationAgent:
    """
    Autonomous agent that explores the knowledge graph to find unseen risks/opportunities.
    
    Memory model:
    - TEMPORARY: Articles/sections loaded via read tools. Each gets own message.
                 Auto-deleted when agent takes any action other than save_excerpt.
    - PERMANENT: Saved excerpts via save_excerpt. Survives entire exploration.
    """
    
    def __init__(self, max_steps: int = 20):
        self.max_steps = max_steps
        self.llm = get_llm(ModelTier.COMPLEX)
    
    def explore_topic(
        self,
        topic_id: str,
        mode: ExplorationMode,
    ) -> ExplorationResult:
        """
        Explore from a topic to find risks or opportunities.
        
        Args:
            topic_id: Starting topic ID
            mode: Whether to hunt for risks or opportunities
            
        Returns:
            ExplorationResult with the finding
        """
        logger.info(f"🔍 Starting exploration for {topic_id} | mode={mode.value}")
        
        # Initialize state
        initial_snapshot = get_topic_snapshot(topic_id)
        state = ExplorationState(
            target_topic_id=topic_id,
            mode=mode,
            current_topic=initial_snapshot,
            visited_topics=[topic_id],
            max_steps=self.max_steps,
        )
        
        # Run exploration loop
        return self._run_loop(state)

    def _ensure_topic_mapping(self, username: str, strategy_id: str, strategy: Dict[str, Any]) -> Dict[str, List[str]]:
        """Ensure strategy has topic mapping; run TopicMapper if missing."""
        from src.exploration_agent.explorer.tools import get_strategy_context
        from src.strategy_agents.topic_mapper.agent import TopicMapperAgent
        from src.api.backend_client import save_strategy_topics

        topic_mapping = strategy.get("topic_mapping") or {
            "primary": [],
            "drivers": [],
            "correlated": [],
        }
        if any(topic_mapping.get(k) for k in ("primary", "drivers", "correlated")):
            return topic_mapping

        logger.info("🧪 No topics mapped yet – running TopicMapperAgent")
        user_input = strategy.get("user_input", {}) or {}
        mapper = TopicMapperAgent()
        mapping = mapper.run(
            asset_text=strategy.get("asset", {}).get("primary", ""),
            strategy_text=user_input.get("strategy_text", ""),
            position_text=user_input.get("position_text", ""),
        )
        normalized = {
            "primary": mapping.get("primary", []),
            "drivers": mapping.get("drivers", []),
            "correlated": mapping.get("correlated", []),
        }
        logger.info("💾 Saving new topic mapping to backend: %s", normalized)
        save_strategy_topics(username, strategy_id, normalized)
        strategy["topic_mapping"] = normalized
        return normalized
    
    def explore_strategy(
        self,
        strategy_user: str,
        strategy_id: str,
        mode: ExplorationMode,
    ) -> ExplorationResult:
        """
        Explore for a strategy by first selecting a starting topic.
        
        Args:
            strategy_id: Strategy ID
            mode: Whether to hunt for risks or opportunities
            
        Returns:
            ExplorationResult with the finding
        """
        from src.exploration_agent.explorer.tools import get_strategy_context
        
        logger.info(f"🔍 Starting exploration for strategy {strategy_id} | mode={mode.value}")
        
        # Get strategy and its topics
        strategy = get_strategy_context(strategy_user, strategy_id)
        if not strategy:
            return ExplorationResult(
                headline="Strategy Not Found",
                rationale=f"Could not find strategy {strategy_id}",
                flow_path="",
                evidence=[],
                target_topic_id="",
                target_strategy_id=strategy_id,
                mode=mode,
                exploration_steps=0,
                success=False,
                error=f"Strategy {strategy_id} not found"
            )
        
        strategy_keys = list(strategy.keys())
        logger.info("📄 Strategy payload keys: %s", strategy_keys)
        user_input = strategy.get("user_input", {}) or {}
        strategy_preview = (user_input.get("strategy_text", "") or "N/A")[:200]
        logger.info("📝 Strategy preview: %s", strategy_preview)
        topic_mapping = self._ensure_topic_mapping(strategy_user, strategy_id, strategy)
        logger.info(
            "🧭 Strategy topic counts | primary=%s drivers=%s correlated=%s",
            len(topic_mapping.get("primary", [])),
            len(topic_mapping.get("drivers", [])),
            len(topic_mapping.get("correlated", [])),
        )
        logger.info("   • primary topics: %s", topic_mapping.get("primary", []))
        logger.info("   • driver topics: %s", topic_mapping.get("drivers", []))
        logger.info("   • correlated topics: %s", topic_mapping.get("correlated", []))
        all_topics = (
            topic_mapping.get("primary", []) +
            topic_mapping.get("drivers", []) +
            topic_mapping.get("correlated", [])
        )
        
        if not all_topics:
            return ExplorationResult(
                headline="No Topics Found",
                rationale=f"Strategy {strategy_id} has no related topics",
                flow_path="",
                evidence=[],
                target_topic_id="",
                target_strategy_id=strategy_id,
                mode=mode,
                exploration_steps=0,
                success=False,
                error="No related topics"
            )
        
        # For now, pick the first primary topic as starting point
        # TODO: Could use LLM to pick most interesting starting point
        start_topic = all_topics[0]
        
        logger.info(f"📍 Strategy {strategy_id} → Starting from topic {start_topic}")
        
        # Initialize state
        initial_snapshot = get_topic_snapshot(start_topic)
        state = ExplorationState(
            target_topic_id=start_topic,
            target_strategy_id=strategy_id,
            mode=mode,
            current_topic=initial_snapshot,
            visited_topics=[start_topic],
            max_steps=self.max_steps,
        )
        
        return self._run_loop(state)
    
    def _run_loop(self, state: ExplorationState) -> ExplorationResult:
        """
        Main exploration loop with message queue architecture.
        
        Key behaviors:
        - Each article/section gets its own message with unique msg_id
        - Temporary content auto-deleted when agent takes non-save action
        - Agent's reasoning (assistant messages) always kept
        """
        # Initialize message queue with system prompt
        system_prompt = EXPLORATION_SYSTEM_PROMPT.format(
            mode=state.mode.value,
            target_topic=state.target_topic_id,
            available_sections=", ".join(ANALYSIS_SECTIONS),
        )
        state.messages.append(MessageEntry(role="system", content=system_prompt))
        
        logger.info("=" * 60)
        logger.info(
            "🚀 EXPLORATION STARTED | target=%s | mode=%s",
            state.target_topic_id,
            state.mode.value,
        )
        logger.info("=" * 60)
        
        while state.step_count < state.max_steps:
            state.step_count += 1
            
            # Log step header
            self._log_step_banner(state)
            
            try:
                # Build step context
                step_context = self._build_step_context(state)
                
                # Add step context as user message
                state.messages.append(MessageEntry(
                    role="user", 
                    content=step_context,
                    msg_id=f"step_{state.step_count}",
                    prunable=False
                ))
                
                # Preview message history before LLM call
                self._log_message_samples(state.messages)
                self._inject_convergence_pressure(state)

                # Call LLM
                response = self._call_llm_with_history(state.messages)
                
                if not response:
                    # Remove previous error messages to avoid accumulation
                    state.messages = [
                        m for m in state.messages 
                        if not (m.content.startswith("⚠️ Invalid response") or m.content.startswith("⚠️ FORMAT ERROR"))
                    ]
                    # Add clear format reminder with example
                    state.messages.append(MessageEntry(
                        role="user",
                        content="""⚠️ FORMAT ERROR: Your response was not valid JSON.

You MUST output ONLY a JSON object like this:
```json
{
    "thinking": "your reasoning here",
    "tool_call": {
        "tool": "read_articles",
        "limit": 3
    }
}
```

Available tools: read_articles, read_section, save_excerpt, think, move_to_topic, draft_finding, finish

Output ONLY the JSON object, no other text.""",
                        prunable=True
                    ))
                    continue
                
                # Add assistant response to history (PERMANENT)
                response_str = json.dumps(response, indent=2)
                state.messages.append(MessageEntry(
                    role="assistant",
                    content=response_str,
                    msg_id=f"response_{state.step_count}",
                    prunable=False
                ))
                
                # Execute tool
                new_messages, is_finish = self._execute_tool(response, state)
                
                if is_finish:
                    logger.info("=" * 60)
                    logger.info(
                        "✅ EXPLORATION COMPLETE | steps=%s | saved_excerpts=%s",
                        state.step_count,
                        len(state.saved_excerpts),
                    )
                    logger.info("=" * 60)
                    return self._build_result(state, success=True)
                
                # Add any new messages from tool execution
                for msg in new_messages:
                    state.messages.append(msg)
                
            except Exception as e:
                logger.error(f"❌ Error in step {state.step_count}: {e}", exc_info=True)
                continue
        
        # Max steps reached
        logger.warning("=" * 60)
        logger.warning(
            "⏰ MAX STEPS REACHED | max=%s | saved_excerpts=%s | has_draft=%s",
            state.max_steps,
            len(state.saved_excerpts),
            bool(state.draft_finding),
        )
        logger.warning("=" * 60)
        return self._build_result(state, success=state.draft_finding is not None)
    
    def _build_step_context(self, state: ExplorationState) -> str:
        """Build the context shown to agent each step."""
        from src.exploration_agent.explorer.prompt import get_convergence_hint
        
        initial_context = get_initial_context(state.current_topic.id, state.mode.value)
        connected_formatted = format_connected_topics(state.current_topic.connected_topics)
        
        # Build saved excerpts section
        if state.saved_excerpts:
            excerpts_section = f"\n💾 **SAVED EXCERPTS** ({len(state.saved_excerpts)} pieces of evidence):\n"
            for i, ex in enumerate(state.saved_excerpts, 1):
                excerpt_preview = ex.excerpt[:100] + "..." if len(ex.excerpt) > 100 else ex.excerpt
                excerpts_section += f"  {i}. [{ex.source_id}] {excerpt_preview}\n"
                excerpts_section += f"     → Why: {ex.why_relevant[:80]}...\n" if len(ex.why_relevant) > 80 else f"     → Why: {ex.why_relevant}\n"
        else:
            excerpts_section = "\n💾 **SAVED EXCERPTS**: None yet - use save_excerpt after reading content!\n"
        
        # Build visited topics section
        visited_section = f"\n🚶 **Visited Topics**: {', '.join(state.visited_topics)}\n" if state.visited_topics else ""
        
        # Build draft finding section
        draft_section = ""
        if state.draft_finding:
            draft_section = f"""
📋 **Current Draft Finding**:
  Headline: {state.draft_finding.get('headline', 'None')}
  Rationale: {state.draft_finding.get('rationale', 'None')}
  Flow Path: {state.draft_finding.get('flow_path', 'None')}
"""
        
        # Get convergence hint (pass temp content status)
        hint = get_convergence_hint(
            state.step_count, 
            state.max_steps, 
            len(state.saved_excerpts), 
            state.draft_finding is not None,
            has_temp_content=len(state.temp_content_ids) > 0
        )
        hint_section = f"\n{hint}\n" if hint else ""
        
        # Temp content warning
        temp_warning = ""
        if state.temp_content_ids:
            temp_warning = f"\n⚠️ **TEMPORARY CONTENT LOADED**: {state.temp_content_ids}\n   Use save_excerpt NOW or this content will be DELETED on your next action!\n"
        
        return f"""
📊 **EXPLORATION STEP {state.step_count}/{state.max_steps}**

{hint_section}
🎯 **Target**: Finding {state.mode.value}s for **{state.target_topic_id}**

📍 **Current Location**: **{state.current_topic.name}** (`{state.current_topic.id}`)

{initial_context}

{connected_formatted}
{excerpts_section}
{visited_section}
{draft_section}
{temp_warning}

What do you want to do next? Output your decision as JSON.
"""
    
    def _inject_convergence_pressure(self, state: ExplorationState) -> None:
        """Inject extra user reminders when nearing max steps without a draft."""
        if state.draft_finding:
            return
        remaining = state.max_steps - state.step_count
        saved = len(state.saved_excerpts)
        # Hard reminder at step >=13 when enough evidence exists
        if state.step_count >= 13 and saved >= 2:
            state.messages.append(MessageEntry(
                role="user",
                content=(
                    "🚨 HARD STOP: You have %s saved excerpt(s) and only %s step(s) left. "
                    "Immediately call draft_finding with inline citations."
                ) % (saved, remaining if remaining >= 0 else 0),
                prunable=False,
            ))
        # Earlier reminder around step 10 if no evidence yet
        elif state.step_count >= 10 and saved < 2:
            state.messages.append(MessageEntry(
                role="user",
                content=(
                    "⚠️ STEP %s/%s: Save at least two excerpts RIGHT NOW or you won't be able to draft in time."
                ) % (state.step_count, state.max_steps),
                prunable=False,
            ))
    
    def _build_result(self, state: ExplorationState, success: bool) -> ExplorationResult:
        """Build the final exploration result."""
        if state.draft_finding:
            return ExplorationResult(
                headline=state.draft_finding.get("headline", "Untitled"),
                rationale=state.draft_finding.get("rationale", ""),
                flow_path=state.draft_finding.get("flow_path", ""),
                evidence=state.saved_excerpts,
                target_topic_id=state.target_topic_id,
                target_strategy_id=state.target_strategy_id,
                mode=state.mode,
                exploration_steps=state.step_count,
                success=success,
            )
        
        return ExplorationResult(
            headline="Exploration Incomplete",
            rationale=f"Completed {state.step_count} steps without drafting a finding",
            flow_path="",
            evidence=state.saved_excerpts,
            target_topic_id=state.target_topic_id,
            target_strategy_id=state.target_strategy_id,
            mode=state.mode,
            exploration_steps=state.step_count,
            success=False,
            error="No finding drafted"
        )
    
    def _delete_temp_content(self, state: ExplorationState) -> List[str]:
        """
        Delete all temporary content messages from history.
        Returns list of deleted IDs for logging.
        """
        if not state.temp_content_ids:
            return []
        
        deleted_ids = state.temp_content_ids.copy()
        
        # Remove messages with temp content IDs
        state.messages = [
            m for m in state.messages 
            if m.msg_id not in state.temp_content_ids
        ]
        
        # Clear temp tracking
        state.temp_content_ids = []
        
        return deleted_ids
    
    def _call_llm_with_history(self, messages: List[MessageEntry]) -> Optional[dict]:
        """
        Call the LLM with full message history and parse JSON response.
        """
        try:
            # Convert MessageEntry list to a single prompt string
            # (LLM router expects string input)
            prompt_parts = []
            for msg in messages:
                if msg.role == "system":
                    prompt_parts.append(msg.content)
                elif msg.role == "user":
                    prompt_parts.append(f"\n--- USER ---\n{msg.content}")
                elif msg.role == "assistant":
                    prompt_parts.append(f"\n--- ASSISTANT ---\n{msg.content}")
            
            full_prompt = "\n".join(prompt_parts)
            
            response = self.llm.invoke(full_prompt)
            
            # Extract content from response
            if hasattr(response, 'content'):
                content = response.content
            elif isinstance(response, dict):
                content = response.get('content', str(response))
            else:
                content = str(response)
            
            # Clean up response (remove markdown code blocks if present)
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            # Parse JSON
            parsed = json.loads(content)

            # Auto-fix: If LLM returned flat tool call without wrapper, wrap it
            if "tool_call" not in parsed and "tool" in parsed:
                logger.warning("⚠️ Response missing 'tool_call' wrapper - auto-fixing")
                logger.warning("   Got: %s", app_logging.truncate_str(str(parsed), 300))

                # Auto-wrap the tool call
                thinking = parsed.pop("thinking", "")
                wrapped = {
                    "thinking": thinking,
                    "tool_call": parsed  # Everything else is the tool call
                }
                logger.info("🔧 Auto-wrapped into correct schema")
                parsed = wrapped

            # Validate structure - must have tool_call with tool
            if "tool_call" not in parsed:
                logger.warning("⚠️ Response missing 'tool_call' key (after auto-fix attempt)")
                logger.warning("   Got: %s", app_logging.truncate_str(str(parsed), 300))
                logger.warning("   Expected schema: {'thinking': '...', 'tool_call': {'tool': '...', ...}}")
                return None
            if not parsed.get("tool_call", {}).get("tool"):
                logger.warning("⚠️ Response has empty tool in tool_call")
                logger.warning("   Got: %s", app_logging.truncate_str(str(parsed), 300))
                logger.warning("   Expected schema: {'thinking': '...', 'tool_call': {'tool': '...', ...}}")
                return None
            
            logger.info(f"🧠 Thinking: {parsed.get('thinking', '')[:100]}...")
            return parsed
            
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ JSON parse failed: {e}")
            # Try to extract tool_call from malformed response
            extracted = self._extract_tool_from_text(content if 'content' in dir() else "")
            if extracted:
                logger.info(f"🔧 Recovered tool from malformed JSON: {extracted.get('tool_call', {}).get('tool')}")
                return extracted
            logger.error(f"Raw content sample: {content[:300] if 'content' in dir() else 'N/A'}...")
            return None
        except Exception as e:
            logger.error(f"LLM call failed: {e}", exc_info=True)
            return None

    def _extract_tool_from_text(self, text: str) -> Optional[dict]:
        """
        MINIMAL BUT POWERFUL extraction from malformed LLM output.

        Strategy:
        1. Brace-match to find complete JSON object
        2. If valid JSON but missing wrapper, auto-wrap it
        3. If no valid JSON, regex extract tool name
        """
        import re

        if not text:
            return None

        logger.debug("   🔧 Attempting extraction from: %s", app_logging.truncate_str(text, 200))

        # Strategy 1: Brace-counting to find outermost complete JSON
        brace_count = 0
        start_idx = None
        for i, char in enumerate(text):
            if char == '{':
                if brace_count == 0:
                    start_idx = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_idx is not None:
                    candidate = text[start_idx:i+1]
                    try:
                        obj = json.loads(candidate)

                        # Perfect structure - return as-is
                        if "tool_call" in obj and obj["tool_call"].get("tool"):
                            logger.info("   ✅ Extracted valid structure")
                            return obj

                        # Missing wrapper - auto-wrap bare tool call
                        # Handles: {"tool": "read_articles", "limit": 3}
                        if "tool" in obj and obj["tool"]:
                            logger.info("   🔧 Wrapped bare tool call: %s", obj.get("tool"))
                            return {
                                "thinking": "Recovered - missing tool_call wrapper",
                                "tool_call": obj
                            }
                    except json.JSONDecodeError:
                        pass
                    start_idx = None

        # Strategy 2: Regex extract tool name as last resort
        tool_pattern = r'"tool"\s*:\s*"(read_articles|read_section|save_excerpt|think|move_to_topic|draft_finding|finish)"'
        match = re.search(tool_pattern, text)
        if match:
            tool_name = match.group(1)
            logger.info("   🔧 Regex extracted tool: %s", tool_name)
            return {
                "thinking": "Recovered - regex extraction",
                "tool_call": {"tool": tool_name}
            }

        logger.warning("   ❌ All extraction strategies failed")
        return None

    # ------------------------------------------------------------------
    # Logging helpers
    # ------------------------------------------------------------------
    def _log_step_banner(self, state: ExplorationState) -> None:
        temp_ids = state.temp_content_ids or []
        saved_count = len(state.saved_excerpts)
        
        logger.info("\n")
        logger.info("=" * 80)
        logger.info("=" * 80)
        logger.info("=" * 80)
        logger.info("█▀▀ STEP %s/%s █▀▀", state.step_count, state.max_steps)
        logger.info("=" * 80)
        logger.info("📍 TOPIC: %s", state.current_topic.id)
        if saved_count > 0:
            showing = min(3, saved_count)
            logger.info("💾 SAVED EXCERPTS: %s%s", saved_count, f" (showing last {showing})" if saved_count > 3 else "")
            for i, exc in enumerate(state.saved_excerpts[-3:], 1):
                logger.info("   [%s] %s (from %s, step %s)", i, exc.source_id, exc.saved_at_topic, exc.saved_at_step)
        else:
            logger.info("💾 SAVED EXCERPTS: 0")
        logger.info("📄 TEMP CONTENT: %s", temp_ids if temp_ids else "(empty)")
        logger.info("-" * 80)

    def _log_message_samples(self, messages: List[MessageEntry], sample_size: int = 3) -> None:
        total = len(messages)
        logger.info("🧾 MESSAGE QUEUE: %s messages (showing last %s)", total, min(sample_size, total))
        for idx, msg in enumerate(messages[-sample_size:], 1):
            snippet = app_logging.truncate_str(msg.content.replace("\n", " "), 150)
            role_icon = {"system": "⚙️", "user": "👤", "assistant": "🤖"}.get(msg.role, "❓")
            logger.info(
                "   %s [%s] %s",
                role_icon,
                msg.msg_id or "-",
                snippet,
            )

    def _log_tool_call(
        self,
        state: ExplorationState,
        tool: str,
        thinking: str,
        payload: dict,
    ) -> None:
        thinking_preview = app_logging.truncate_str(thinking, 120)
        logger.info("")
        logger.info("┌─ 🔧 TOOL: %s", tool.upper())
        logger.info("│  💭 %s", thinking_preview)
        # Show relevant payload params
        params = {k: v for k, v in payload.items() if k != "tool"}
        if params:
            for k, v in params.items():
                v_str = app_logging.truncate_str(str(v), 100)
                logger.info("│  📎 %s: %s", k, v_str)

    def _log_tool_effect(self, action: str, **details: object) -> None:
        filtered = {k: v for k, v in details.items() if v not in (None, [], {})}
        if filtered:
            for k, v in filtered.items():
                logger.info("│  ✓ %s: %s", k, v)
        logger.info("└─ ✅ %s", action)
    
    def _execute_tool(self, response: dict, state: ExplorationState) -> Tuple[List[MessageEntry], bool]:
        """
        Execute the tool call from the LLM response.
        
        Key behavior:
        - save_excerpt: Saves excerpts, keeps temp content
        - Any other tool: Deletes temp content first, then executes
        
        Returns:
            (new_messages, is_finish)
            - new_messages: List of MessageEntry to add to history
            - is_finish: True if agent called finish
        """
        thinking = response.get("thinking", "")
        tool_call = response.get("tool_call", {})
        tool_name = tool_call.get("tool", "")
        
        if not tool_name:
            logger.warning("⚠️ Empty tool call received")
            return [MessageEntry(
                role="user",
                content="⚠️ Your response had no tool. Please output JSON with a valid tool call.",
                prunable=True
            )], False
        
        # Use the new tool call logger
        self._log_tool_call(state, tool_name, thinking, tool_call)
        
        # =====================================================================
        # SAVE_EXCERPT: Special handling - does NOT delete temp content
        # =====================================================================
        if tool_name == "save_excerpt":
            saves = tool_call.get("saves", [])
            if not saves:
                logger.warning("   ⚠️ No saves provided")
                return [MessageEntry(
                    role="user",
                    content="⚠️ save_excerpt requires 'saves' list with {source_id, excerpt, why_relevant}",
                    prunable=True
                )], False
            
            saved_ids = []
            errors = []
            
            for save in saves:
                source_id = save.get("source_id", "")
                excerpt = save.get("excerpt", "")
                why_relevant = save.get("why_relevant", "")
                
                # Validate source_id is in temp content
                if source_id not in state.temp_content_ids:
                    errors.append(f"'{source_id}' not in temp content")
                    continue
                
                # Save the excerpt
                state.saved_excerpts.append(SavedExcerpt(
                    excerpt=excerpt,
                    source_id=source_id,
                    source_type="article" if source_id.startswith("art_") else "section",
                    why_relevant=why_relevant,
                    saved_at_topic=state.current_topic.id,
                    saved_at_step=state.step_count
                ))
                saved_ids.append(source_id)
                logger.info("│  💾 SAVED: %s", source_id)
                logger.info("│     excerpt: %s", app_logging.truncate_str(excerpt, 80))
                logger.info("│     why: %s", app_logging.truncate_str(why_relevant, 60))
            
            # Log results
            self._log_tool_effect(
                "save_excerpt",
                saved=saved_ids or "none",
                errors=errors or None,
                total_saved=len(state.saved_excerpts),
                temp_ids=state.temp_content_ids,
            )
            
            # Build response message
            msg = f"💾 **Saved {len(saved_ids)} excerpt(s)**: {saved_ids}\n"
            msg += f"   Total evidence: {len(state.saved_excerpts)} excerpts\n"
            if errors:
                msg += f"   ⚠️ Errors: {errors}\n"
            msg += f"\n⚠️ Temp content still available: {state.temp_content_ids}\n"
            msg += "   Save more or take another action (which will delete temp content)."
            
            return [MessageEntry(
                role="user",
                content=msg,
                msg_id=f"saved_{state.step_count}",
                prunable=False
            )], False
        
        # =====================================================================
        # ALL OTHER TOOLS: Delete temp content first
        # =====================================================================
        deleted_ids = self._delete_temp_content(state)
        if deleted_ids:
            logger.info("│  🗑️  AUTO-DELETE: %s", deleted_ids)
        
        # ----- READ_SECTION -----
        if tool_name == "read_section":
            section = tool_call.get("section", "")
            content, source_id, success = read_section(state.current_topic.id, section)
            
            if not success:
                return [MessageEntry(
                    role="user",
                    content=content,  # Error message
                    prunable=True
                )], False
            
            # Track as temp content
            state.temp_content_ids = [source_id]
            
            self._log_tool_effect(
                "read_section",
                source_id=source_id,
                chars=len(content),
                temp_ids=state.temp_content_ids,
            )
            
            # Create message for this section
            msg_content = f"""📖 **TEMPORARY CONTENT** (ID: {source_id})

{content}

⚠️ This content will be DELETED on your next action (unless you save_excerpt).
To save: {{"tool": "save_excerpt", "saves": [{{"source_id": "{source_id}", "excerpt": "...", "why_relevant": "..."}}]}}"""
            
            return [MessageEntry(
                role="user",
                content=msg_content,
                msg_id=source_id,
                prunable=True
            )], False
        
        # ----- READ_ARTICLES -----
        elif tool_name == "read_articles":
            limit = tool_call.get("limit", 3)
            articles, source_ids = read_articles(state.current_topic.id, limit)
            
            if not articles:
                return [MessageEntry(
                    role="user",
                    content=f"📭 No articles found for topic '{state.current_topic.id}'",
                    prunable=True
                )], False
            
            # Track as temp content (include summary message ID)
            state.temp_content_ids = ["articles_summary"] + source_ids
            
            # Log each article being loaded
            logger.info("│  📥 LOADING %s ARTICLES:", len(articles))
            for art in articles:
                logger.info("│     • %s: %s (%s chars)", art["source_id"], app_logging.truncate_str(art["title"], 50), len(art["content"]))
            self._log_tool_effect(
                "read_articles",
                article_count=len(articles),
                temp_ids=state.temp_content_ids,
            )
            
            # Create ONE message per article
            messages = []
            
            # First, add summary message
            summary = f"📰 **LOADED {len(articles)} ARTICLES** (IDs: {source_ids})\n\n"
            summary += "⚠️ These are TEMPORARY. Use save_excerpt to keep what matters.\n"
            summary += "Example: {\"tool\": \"save_excerpt\", \"saves\": [{\"source_id\": \"art_XXX\", \"excerpt\": \"...\", \"why_relevant\": \"...\"}]}\n"
            
            messages.append(MessageEntry(
                role="user",
                content=summary,
                msg_id="articles_summary",
                prunable=True
            ))
            
            # Then, one message per article
            for article in articles:
                source_id = article["source_id"]
                title = article["title"]
                content = article["content"]
                
                msg_content = f"""───────────────────────────────────────
📄 **{source_id}**: {title}
───────────────────────────────────────
{content}
"""
                messages.append(MessageEntry(
                    role="user",
                    content=msg_content,
                    msg_id=source_id,
                    prunable=True
                ))
            
            return messages, False
        
        # ----- THINK -----
        elif tool_name == "think":
            thought = tool_call.get("thought", "")
            self._log_tool_effect("think", thought_chars=len(thought))
            
            return [MessageEntry(
                role="user",
                content=f"💭 **Thought recorded.** Continue with your next action.",
                msg_id=f"think_{state.step_count}",
                prunable=False
            )], False
        
        # ----- MOVE_TO_TOPIC -----
        elif tool_name == "move_to_topic":
            topic_id = tool_call.get("topic_id", "")
            reason = tool_call.get("reason", "")
            
            # Validate
            connected_ids = [t["id"] for t in state.current_topic.connected_topics]
            if topic_id not in connected_ids:
                logger.warning(f"   ⚠️ Invalid topic: {topic_id}")
                return [MessageEntry(
                    role="user",
                    content=f"⚠️ Cannot move to '{topic_id}' - not connected. Choose from: {connected_ids[:5]}...",
                    prunable=True
                )], False
            
            # Move
            old_topic = state.current_topic.id
            new_snapshot = get_topic_snapshot(topic_id)
            state.current_topic = new_snapshot
            state.visited_topics.append(topic_id)
            
            self._log_tool_effect(
                "move_to_topic",
                from_topic=old_topic,
                to_topic=topic_id,
                reason=app_logging.truncate_str(reason, 120),
            )
            
            return [], False  # Next step context shows new topic
        
        # ----- DRAFT_FINDING -----
        elif tool_name == "draft_finding":
            headline = tool_call.get("headline", "")
            rationale = tool_call.get("rationale", "")
            flow_path = tool_call.get("flow_path", "")

            # CRITICAL: Check for missing citations BEFORE accepting draft
            missing_sources_msg = self._check_and_fetch_missing_citations(rationale, state)

            # If missing citations found, REJECT this draft immediately
            if missing_sources_msg:
                logger.warning("❌ Draft rejected: Missing citations detected before storing")
                return [missing_sources_msg], False

            # All citations valid - store draft
            state.draft_finding = {
                "headline": headline,
                "rationale": rationale,
                "flow_path": flow_path,
            }

            self._log_tool_effect(
                "draft_finding",
                headline=app_logging.truncate_str(headline, 120),
                flow=app_logging.truncate_str(flow_path, 120),
            )

            # Run critic on FIRST draft only (not on revisions after feedback)
            # This gives agent 1 feedback cycle to improve before final submission
            if not state.critic_feedback_received:
                remaining_steps = self.max_steps - state.step_count
                logger.info("🔍 Draft at step %d/%d - Running CRITIC (first draft, %d steps remaining)...",
                           state.step_count, self.max_steps, remaining_steps)

                feedback_msg = self._run_critic(state)

                state.critic_feedback_received = True  # Mark that critic has run
                return [feedback_msg], False
            else:
                # Subsequent drafts after critic feedback - no more critic
                logger.info("✅ Revised draft after critic feedback (step %d/%d)",
                           state.step_count, self.max_steps)
                return [MessageEntry(
                    role="user",
                    content=f"📝 **Revised finding drafted!**\n\nHeadline: {headline}\n\nCall 'finish' when satisfied, or continue exploring to strengthen.",
                    msg_id=f"draft_{state.step_count}",
                    prunable=False
                )], False
        
        # ----- FINISH -----
        elif tool_name == "finish":
            if not state.draft_finding:
                logger.warning("   ⚠️ Finish without draft")
                return [MessageEntry(
                    role="user",
                    content="⚠️ Cannot finish without a draft. Call draft_finding first.",
                    prunable=True
                )], False
            
            self._log_tool_effect("finish", draft_exists=bool(state.draft_finding))
            return [], True
        
        # ----- SUGGEST_LINK -----
        elif tool_name == "suggest_link":
            source = tool_call.get("source_topic", "")
            target = tool_call.get("target_topic", "")
            rel_type = tool_call.get("relationship_type", "")
            self._log_tool_effect(
                "suggest_link",
                source=source,
                target=target,
                relationship=rel_type,
            )
            
            return [MessageEntry(
                role="user",
                content=f"🔗 **Link suggestion noted**: {source} -{rel_type}-> {target}",
                prunable=True
            )], False
        
        # ----- UNKNOWN -----
        else:
            logger.warning(f"   ⚠️ Unknown tool: {tool_name}")
            return [MessageEntry(
                role="user",
                content=f"⚠️ Unknown tool '{tool_name}'. Valid tools: read_section, read_articles, save_excerpt, think, move_to_topic, draft_finding, finish",
                prunable=True
            )], False

    def _run_critic(self, state: ExplorationState) -> MessageEntry:
        """
        Run mid-exploration critic and return feedback as USER message.

        Called when agent drafts before 50% progress.
        """
        from src.exploration_agent.critic import CriticAgent

        critic = CriticAgent()

        feedback = critic.review(
            finding_headline=state.draft_finding["headline"],
            finding_rationale=state.draft_finding["rationale"],
            finding_flow_path=state.draft_finding["flow_path"],
            saved_excerpts=state.saved_excerpts,
            current_step=state.step_count,
            max_steps=self.max_steps
        )

        # Format feedback as user message
        verdict_emoji = {
            "continue_exploring": "🔍",
            "revise_draft": "✏️",
            "ready_to_finish": "✅"
        }.get(feedback.verdict, "📋")

        # Build sharp, directive feedback message
        content_parts = [
            f"{verdict_emoji} **CRITIC REVIEW** - Quality Score: {feedback.quality_score:.2f}/1.0",
            "",
            f"**VERDICT: {feedback.verdict.replace('_', ' ').upper()}**",
            ""
        ]

        # Critical issues first - these MUST be fixed
        if feedback.citation_issues or feedback.chain_gaps:
            content_parts.append("🚨 **CRITICAL ISSUES - MUST FIX BEFORE CALLING FINISH:**")
            content_parts.append("")

            if feedback.citation_issues:
                content_parts.append("**Missing/Wrong Citations:**")
                for i, issue in enumerate(feedback.citation_issues, 1):
                    content_parts.append(f"  {i}. {issue}")
                content_parts.append("")

            if feedback.chain_gaps:
                content_parts.append("**Chain Gaps (No Evidence):**")
                for i, gap in enumerate(feedback.chain_gaps, 1):
                    content_parts.append(f"  {i}. {gap}")
                content_parts.append("")

        # Actionable next steps - EMPHASIZE THE ACTION
        if feedback.suggestions:
            content_parts.append("💡 **YOUR ACTION PLAN (FOLLOW THESE STEPS):**")
            for i, sug in enumerate(feedback.suggestions, 1):
                content_parts.append(f"  {i}. {sug}")
            content_parts.append("")

        content_parts.append(f"**Why**: {feedback.reasoning}")
        content_parts.append("")

        # Add explicit reminder based on verdict
        if feedback.verdict == "revise_draft":
            content_parts.append("⚠️ **MANDATORY NEXT ACTION: Call draft_finding again with fixes. DO NOT call finish until ALL issues are resolved!**")
        elif feedback.verdict == "continue_exploring":
            content_parts.append("⚠️ **MANDATORY NEXT ACTION: Keep exploring to gather missing evidence, then call draft_finding again.**")
        elif feedback.verdict == "ready_to_finish":
            content_parts.append("✅ **You may now call finish to submit this finding.**")

        return MessageEntry(
            role="user",
            content="\n".join(content_parts),
            msg_id=f"critic_feedback_{state.step_count}",
            prunable=False
        )

    def _check_and_fetch_missing_citations(
        self,
        rationale: str,
        state: ExplorationState
    ) -> Optional[MessageEntry]:
        """
        Check if rationale cites sources that aren't in saved_excerpts.
        If missing sources are found, try to fetch them from temp content or log warning.

        Returns a message to agent if action needed, None otherwise.
        """
        import re

        # Extract all (source_id) citations from rationale
        cited_sources = set(re.findall(r'\(([a-z_0-9]+)\)', rationale))

        if not cited_sources:
            return None  # No citations found

        # Get all saved source IDs
        saved_sources = set(exc.source_id for exc in state.saved_excerpts)

        # Find missing citations
        missing = cited_sources - saved_sources

        if not missing:
            return None  # All cited sources are saved ✅

        # We have missing citations!
        logger.warning("⚠️ Found %d cited sources not in saved excerpts: %s",
                      len(missing), list(missing))

        # Try to recover: check if any are in temp_content_ids
        available_in_temp = [s for s in missing if s in state.temp_content_ids]

        warnings = []
        warnings.append("🚨 **DRAFT REJECTED - CITATION ERROR!**")
        warnings.append("")
        warnings.append(f"❌ You cited {len(missing)} source(s) in your rationale that you haven't saved as excerpts:")
        warnings.append("")

        for source_id in missing:
            if source_id in available_in_temp:
                warnings.append(f"  • `{source_id}` → Currently loaded! Save an excerpt from this NOW!")
            else:
                warnings.append(f"  • `{source_id}` → NOT loaded. You must read this and save an excerpt!")

        warnings.append("")
        warnings.append("⚠️ **MANDATORY NEXT STEPS:**")
        warnings.append("1. For each missing source, use save_excerpt to save the relevant text")
        warnings.append("2. Then call draft_finding again with proper citations")
        warnings.append("")
        warnings.append("**CRITICAL**: The final critic will REJECT any finding with unsaved citations!")
        warnings.append("Every claim in your rationale MUST be backed by a saved excerpt.")

        return MessageEntry(
            role="user",
            content="\n".join(warnings),
            msg_id=f"missing_citations_{state.step_count}",
            prunable=False
        )
