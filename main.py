"""
main.py — Intelli-Credit entry points.

Usage:
  streamlit run app.py          → Streamlit UI (default)
  python main.py a2a            → Start A2A Protocol server (port 5000)
  python main.py                → Print usage info
"""
import sys


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "a2a":
        from a2a.server import run_a2a_server
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
        run_a2a_server(port=port)
    else:
        print("Intelli-Credit | AI-Powered Corporate Credit Appraisal Engine")
        print()
        print("Usage:")
        print("  streamlit run app.py      → Launch Streamlit UI")
        print("  python main.py a2a        → Start A2A Protocol server")
        print("  python main.py a2a 8080   → A2A server on custom port")


if __name__ == "__main__":
    main()
