import os
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic
from harness.tools import registry
from harness.memory import load_agents_md, consolidate_memory
from harness.config import MODEL, MAX_TOKENS, STEP_BUDGET, BUDEGET_HIT_MESSAGE

load_dotenv()

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "prompt_system.txt").read_text()


def main():
    messages = []
    tools = registry.get_schemas()
    agents_md = load_agents_md()
    system = [
        {"type": "text", "text": SYSTEM_PROMPT},
        {"type": "text", "text": agents_md},
    ]
    
    try:
        _run_turns(messages, tools, system)
    except (KeyboardInterrupt, EOFError):
        print("\nConsolidating memory before exit...")
        consolidate_memory(client, MODEL)


def _run_turns(messages, tools, system):
    while True:
        user_input = input("You: ")
        messages.append({"role": "user", "content": user_input})
        step_count=0
        while True:
            if step_count >= STEP_BUDGET:
                messages.append({"role": "user", "content": BUDEGET_HIT_MESSAGE})
                response = client.messages.create(
                        model=MODEL,
                        max_tokens=1024,
                        system=system,
                        messages=messages,
                        tools=tools,
                        tool_choice={"type": "none"},
                    )
                messages.append({"role": "assistant", "content": response.content})
                has_text = False
                for block in response.content:
                    if block.type == "text" and block.text:
                            print(f"Agent: {block.text}")
                            has_text = True
                if not has_text:
                        # Content should never be empty here — max_tokens cut the response
                        # short, or something upstream is broken. Fail loudly instead of
                        # silently showing the user nothing.
                    raise RuntimeError(
                            "Step budget reached but the forced final response has no "
                            "text content. Check the API response and max_tokens."
                        )
                break

            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=messages,
                tools = tools,
                system=system
            )
            has_text = False
            messages.append({"role": "assistant", "content": response.content})
            
            for block in response.content:
                if block.type == "text":
                    print(f"Agent: {block.text}")
                    has_text = True
            tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
            if not tool_use_blocks:
                    if not has_text:
                        if not has_text:
                            print(f"[debug] stop_reason={response.stop_reason!r}")
                            print(f"[debug] content={response.content!r}")
                            raise RuntimeError(
                                "Loop terminated with no tool calls and no text content. "
                                "Check the API response and the termination logic."
        )
                        
                    break
            tool_results = []
            for call in tool_use_blocks:
                result = registry.dispatch(call.name, call.input)
                print(f"  [observation] {result}")                       # Observe
                tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": result,
                    })
            messages.append({"role": "user", "content": tool_results})
            step_count += 1


if __name__ == "__main__":
    main()
