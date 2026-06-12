#!/usr/bin/env python3
"""
Bridge: TS server вызывает Python бизнес-логику через subprocess.

Использование из Node.js:
    spawn('python3', ['-m', 'bookcabinet.bridge', 'issue', bookRfid, userRfid])
    spawn('python3', ['-m', 'bookcabinet.bridge', 'return', bookRfid])
    spawn('python3', ['-m', 'bookcabinet.bridge', 'home'])
    spawn('python3', ['-m', 'bookcabinet.bridge', 'stop'])
    spawn('python3', ['-m', 'bookcabinet.bridge', 'issue_sequence', cellAddress])
    spawn('python3', ['-m', 'bookcabinet.bridge', 'return_sequence', cellAddress])

Вывод: JSON на stdout (one JSON object per line).
Progress events: {"type": "progress", "step": N, "label": "...", "status": "running"|"done"}
Final result:    {"type": "result", "success": true|false, ...}
"""
import sys
import json
import asyncio

# Добавляем путь для импорта bookcabinet и tools
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))


def output(data: dict):
    print(json.dumps(data, ensure_ascii=False), flush=True)


async def cmd_issue(book_rfid: str, user_rfid: str):
    from bookcabinet.business.issue import issue_service

    def on_progress(event):
        output({'type': 'progress', **event})

    result = await issue_service.issue_book(book_rfid, user_rfid, on_progress=on_progress)
    output({'type': 'result', **result})


async def cmd_return(book_rfid: str):
    from bookcabinet.business.return_book import return_service

    def on_progress(event):
        output({'type': 'progress', **event})

    result = await return_service.return_book(book_rfid, on_progress=on_progress)
    output({'type': 'result', **result})


async def cmd_home():
    from bookcabinet.mechanics.algorithms import algorithms
    success = await algorithms.init_home()
    output({'type': 'result', 'success': success})


async def cmd_stop():
    from bookcabinet.mechanics.algorithms import algorithms
    algorithms.stop()
    output({'type': 'result', 'success': True, 'message': 'Emergency stop activated'})


async def cmd_status():
    from bookcabinet.mechanics.algorithms import algorithms
    state = algorithms.get_state()
    output({'type': 'result', 'success': True, **state})


_MOCK_SEQUENCE_STEPS = [
    "Homing XY", "Moving to cell", "Opening inner shutter", "Extending tray back",
    "Closing inner shutter", "Moving to window", "Opening inner shutter at window",
    "Locking front, extending tray", "Opening outer shutter", "Waiting for user",
    "Closing outer shutter", "Retracting tray", "Closing inner shutter", "Homing",
]


async def _mock_sequence(cell_address: str):
    """MOCK_MODE: имитация механической последовательности (формат событий
    совпадает с tools/book_sequences.py) — для разработки UI без железа."""
    for i, label in enumerate(_MOCK_SEQUENCE_STEPS, 1):
        extra = {'wait_seconds': 10} if i in (9, 10) else {}
        output({'type': 'progress', 'step': i, 'label': label, 'status': 'running', **extra})
        await asyncio.sleep(1.5 if i == 10 else 0.4)
        output({'type': 'progress', 'step': i, 'label': label, 'status': 'done', **extra})
    output({'type': 'result', 'success': True, 'mock': True, 'cell': cell_address})


async def cmd_issue_sequence(cell_address: str):
    """Run the full mechanical issue sequence for a cell address (e.g. '1.1.5')."""
    from bookcabinet.config import MOCK_MODE
    if MOCK_MODE:
        await _mock_sequence(cell_address)
        return
    from book_sequences import BookSequenceRunner

    def on_progress(**event):
        output({'type': 'progress', **event})

    runner = BookSequenceRunner(progress_cb=on_progress)
    try:
        result = await runner.issue_book_sequence(cell_address)
        output({'type': 'result', **result})
    finally:
        runner.close()


async def cmd_return_sequence(cell_address: str):
    """Run the full mechanical return sequence, placing book into cell_address."""
    from bookcabinet.config import MOCK_MODE
    if MOCK_MODE:
        await _mock_sequence(cell_address)
        return
    from book_sequences import BookSequenceRunner

    def on_progress(**event):
        output({'type': 'progress', **event})

    runner = BookSequenceRunner(progress_cb=on_progress)
    try:
        result = await runner.return_book_sequence(cell_address)
        output({'type': 'result', **result})
    finally:
        runner.close()


async def cmd_issue_workflow(source: str, window: str, rfid: str, title: str, speed: str):
    """Full production issue workflow with RFID verify, parallel shutters, error recovery."""
    from bookcabinet.workflows.issue import IssueWorkflow

    def on_progress(**event):
        output({'type': 'progress', **event})

    wf = IssueWorkflow(progress_cb=on_progress, speed=int(speed or 2600))
    result = await wf.run(
        source_address=source,
        window_address=window or '1.2.9',
        expected_book_rfid=rfid or None,
        book_title=title or '',
    )
    output({'type': 'result', **result})


async def cmd_return_workflow(target: str, window: str, rfid: str, title: str, speed: str):
    """Full production return workflow with RFID verify, parallel shutters, error recovery."""
    from bookcabinet.workflows.return_book import ReturnWorkflow

    def on_progress(**event):
        output({'type': 'progress', **event})

    wf = ReturnWorkflow(progress_cb=on_progress, speed=int(speed or 2600))
    result = await wf.run(
        target_address=target,
        window_address=window or '1.2.9',
        expected_book_rfid=rfid or None,
        book_title=title or '',
    )
    output({'type': 'result', **result})


COMMANDS = {
    'issue': lambda args: cmd_issue(args[0], args[1]),
    'return': lambda args: cmd_return(args[0]),
    'home': lambda args: cmd_home(),
    'stop': lambda args: cmd_stop(),
    'status': lambda args: cmd_status(),
    'issue_sequence': lambda args: cmd_issue_sequence(args[0]),
    'return_sequence': lambda args: cmd_return_sequence(args[0]),
    'issue_workflow': lambda args: cmd_issue_workflow(
        args[0],
        args[1] if len(args) > 1 else '1.2.9',
        args[2] if len(args) > 2 else '',
        args[3] if len(args) > 3 else '',
        args[4] if len(args) > 4 else '2600',
    ),
    'return_workflow': lambda args: cmd_return_workflow(
        args[0],
        args[1] if len(args) > 1 else '1.2.9',
        args[2] if len(args) > 2 else '',
        args[3] if len(args) > 3 else '',
        args[4] if len(args) > 4 else '2600',
    ),
}


def main():
    if len(sys.argv) < 2:
        output({'type': 'error', 'message': f'Usage: bridge.py <command> [args...]\nCommands: {", ".join(COMMANDS.keys())}'})
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    if command not in COMMANDS:
        output({'type': 'error', 'message': f'Unknown command: {command}'})
        sys.exit(1)

    try:
        asyncio.run(COMMANDS[command](args))
    except Exception as e:
        output({'type': 'error', 'message': str(e)})
        sys.exit(1)


if __name__ == '__main__':
    main()
