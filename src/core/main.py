"""Hospital Ángeles IA — Agente Contable CLI entry point."""

from dotenv import load_dotenv

from src.core.gemini_client import create_chat, ensure_gemini_configured, load_soul, GeminiModel

load_dotenv()


def boot() -> None:
    """Boot sequence: configure API, load persona, verify connectivity."""

    ensure_gemini_configured()
    print("[Agente Contable] API key loaded.")

    # 2. Load and verify SOUL.md
    soul = load_soul()
    print(f"[Agente Contable] SOUL.md loaded ({len(soul):,} chars).")

    # 3. Create agent and verify Gemini responds in character
    chat = create_chat(model=GeminiModel.FLASH)
    response = chat.send_message(
        "Preséntate en una línea. ¿Quién eres y cuál es tu función?"
    )
    print(f"[Agente Contable] Agent says: {response.text.strip()}")
    print("[Agente Contable] Phase 2 complete. Persona active.")


def interactive_demo() -> None:
    """Simple interactive loop for testing the persona."""
    ensure_gemini_configured()

    chat = create_chat(model=GeminiModel.FLASH)
    print("\n" + "=" * 60)
    print("  Agente Contable — demo interactivo")
    print("  Escribe 'salir' para terminar.")
    print("=" * 60 + "\n")

    while True:
        user_input = input("Doctor > ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("salir", "exit", "quit"):
            print("[Agente Contable] Sesión terminada.")
            break

        response = chat.send_message(user_input)
        print(f"Agente Contable > {response.text.strip()}\n")


def main() -> None:
    print("[Agente Contable] Booting...")
    boot()
    interactive_demo()


if __name__ == "__main__":
    main()
