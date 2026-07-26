# app2/firewall/cost_controller.py
import os
import re
from datetime import date
from typing import Any

from app2.db.models import FirewallDailyUsage
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class CostController:
    def __init__(
        self,
        daily_limit_units: int | None = None,
        max_units_per_request: int | None = None,
    ):
        self.daily_limit_units = int(
            daily_limit_units or os.getenv("FIREWALL_DAILY_LIMIT_UNITS", "1000")
        )
        self.max_units_per_request = int(
            max_units_per_request or os.getenv("FIREWALL_MAX_UNITS_PER_REQUEST", "5")
        )

        # Broad query patterns (relaxed)
        self.broad_patterns = [
            r"\beverything\b",
            r"\ball posts\b",
            r"\ball templates\b",
            r"\ball content\b",
            r"\ball of them\b",
            "همه چیز",
            "همه قالب",
            "همه پست",
            "همه محصولات",
            "هر چی داری",
            "هرچی داری",
        ]

    def is_broad_query(self, query: str) -> bool:
        if not query:
            return False
        q = query.lower()
        if len(q.split()) >= 20:
            return True
        return any(re.search(p, q) for p in self.broad_patterns)

    def estimate_units(self, query: str) -> int:
        if not query:
            return 1
        tokens = len(query.split())
        units = 1
        if tokens > 10:
            units += 1
        if tokens > 18:
            units += 1
        return min(units, self.max_units_per_request)

    def check(self, db: Session, query: str) -> dict[str, Any]:
        q = (query or "").strip()
        cost_units = self.estimate_units(q)

        # Broad query block
        if self.is_broad_query(q):
            return {
                "allowed": False,
                "reason": "too_broad_query",
                "cost_units": cost_units,
            }

        today = date.today()

        try:
            # Get or create daily row
            row = (
                db.query(FirewallDailyUsage)
                .filter(FirewallDailyUsage.day == today)
                .with_for_update()
                .one_or_none()
            )

            if row is None:
                row = FirewallDailyUsage(
                    day=today,
                    used_units=0,
                    daily_limit=self.daily_limit_units,
                )
                db.add(row)
                db.flush()

            # Check limit
            if row.used_units + cost_units > row.daily_limit:
                db.rollback()
                return {
                    "allowed": False,
                    "reason": "daily_cost_limit_exceeded",
                    "cost_units": cost_units,
                    "used_today": row.used_units,
                    "daily_limit": row.daily_limit,
                }

            # Update usage
            row.used_units += cost_units
            db.commit()

            return {
                "allowed": True,
                "reason": "ok",
                "cost_units": cost_units,
                "used_today": row.used_units,
                "daily_limit": row.daily_limit,
            }

        except SQLAlchemyError as e:
            db.rollback()
            return {
                "allowed": True,
                "reason": f"cost_controller_db_error:{e!s}",
                "cost_units": cost_units,
                "used_today": 0,
                "daily_limit": self.daily_limit_units,
            }

        except Exception as e:
            db.rollback()
            return {
                "allowed": True,
                "reason": f"cost_controller_error_fallback:{e!s}",
                "cost_units": cost_units,
                "used_today": 0,
                "daily_limit": self.daily_limit_units,
            }
