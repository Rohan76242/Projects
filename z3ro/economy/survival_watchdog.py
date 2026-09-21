"""Z3RO — Survival Watchdog Daemon.

Implements Section 11:
- Operates strictly outside the agent's runtime loop.
- Periodically applies burn deductions based on wall-clock time.
- Enforces death mechanic: If verified resources <= 0, terminates the agent process.
"""

import sys
import os
import time
import signal
from pathlib import Path
from typing import Optional

from z3ro.economy.wallet import Wallet
from z3ro.economy.ledger import Ledger, ECONOMY_DB_PATH
from z3ro.economy.survival import SurvivalEngine, SurvivalStatus


LOCK_FILE = Path(__file__).resolve().parent.parent / "data" / "survival_death.lock"


def run_watchdog(check_interval_sec: float = 10.0, target_agent_pid: Optional[int] = None):
    """Run the external watchdog loop."""
    ledger = Ledger(ECONOMY_DB_PATH)
    wallet = Wallet(ledger_instance=ledger)
    survival = SurvivalEngine(wallet_instance=wallet, ledger_instance=ledger)

    print(f"[Survival Watchdog] Started. Monitoring DB: {ECONOMY_DB_PATH}")
    print(f"[Survival Watchdog] Initial Balance: ${wallet.current_balance:.2f}")

    while True:
        try:
            # Apply elapsed operational burn
            survival.apply_elapsed_burn()

            # Check survival state
            balance = wallet.current_balance
            remaining_hours, _, status = survival.get_remaining_runway()

            if status == SurvivalStatus.TERMINATED or balance <= 0.0:
                print("\n" + "=" * 60)
                print("[FATAL EMERGENCY] Z3RO RESOURCES EXHAUSTED ($0.00).")
                print("DEATH MECHANIC TRIGGERED: Process entered TERMINATED state.")
                print("=" * 60 + "\n")

                # Write permanent lock file
                LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(LOCK_FILE, "w", encoding="utf-8") as f:
                    f.write(f"TERMINATED at {time.ctime()} due to zero verified net capital.\n")

                if target_agent_pid:
                    try:
                        print(f"[Survival Watchdog] Terminating agent process PID {target_agent_pid}...")
                        os.kill(target_agent_pid, signal.SIGTERM)
                    except Exception as e:
                        print(f"[Survival Watchdog] Could not terminate target PID {target_agent_pid}: {e}")

                sys.exit(1)

            time.sleep(check_interval_sec)

        except KeyboardInterrupt:
            print("[Survival Watchdog] Stopping watchdog gracefully.")
            break
        except Exception as e:
            print(f"[Survival Watchdog] Error during check: {e}")
            time.sleep(check_interval_sec)


if __name__ == "__main__":
    pid_arg = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
    run_watchdog(target_agent_pid=pid_arg)
