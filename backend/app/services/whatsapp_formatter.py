from datetime import date
from typing import List, Dict, Any, Optional


class WhatsAppFormatter:
    """
    Generates pre-formatted WhatsApp messages from approved hourly reports.
    Designed for instant 1-click copy-pasting to agency leadership groups.
    """

    @staticmethod
    def format_report(
        workspace_name: str,
        reporting_date: date,
        hour_slot: str,
        metrics: List[Dict[str, Any]],
        summary_totals: Dict[str, Any],
        approver_name: Optional[str] = None
    ) -> str:
        """
        Formats report data into standard WhatsApp text with emojis, bolding, and dividers.
        """
        date_str = reporting_date.strftime("%d-%b-%Y")
        
        # Convert hour slot (e.g., '15:00') to 12-hour AM/PM format (e.g., '03:00 PM IST')
        try:
            hour_part, min_part = hour_slot.split(":")
            h = int(hour_part)
            ampm = "AM" if h < 12 else "PM"
            display_h = h if 1 <= h <= 12 else (h - 12 if h > 12 else 12)
            time_display = f"{display_h:02d}:{min_part} {ampm} IST"
        except Exception:
            time_display = f"{hour_slot} IST"

        lines = [
            f"📊 *{workspace_name} — MIS Report*",
            f"📅 *Date:* {date_str} | *Slot:* {time_display}",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ]

        # Recruiter line items
        for m in metrics:
            name = m.get("recruiter_name", "Unknown Recruiter")
            roles_list = m.get("job_roles", [])
            roles_str = f" ({', '.join(roles_list)})" if roles_list else ""
            
            total = m.get("total_calls", 0)
            conn = m.get("connected_calls", 0)
            not_conn = m.get("not_connected_calls", 0)
            rate = m.get("connected_rate", 0.0)
            interviews = m.get("next_day_interviews", 0)

            lines.append(f"👤 *{name}*{roles_str}")
            lines.append(f"   Calls: {total} ({conn} Conn / {not_conn} Not Conn) | {rate:.1f}% | 🎯 Intrvws: {interviews}")
            lines.append("")

        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        # Team Summary
        tot_calls = summary_totals.get("total_calls", 0)
        team_rate = summary_totals.get("connected_rate", 0.0)
        tot_interviews = summary_totals.get("next_day_interviews", 0)
        
        lines.append(f"📈 *Team Total:* {tot_calls} Calls | {team_rate:.1f}% Conn Rate | 🎯 {tot_interviews} Next-Day Interviews")
        
        if approver_name:
            lines.append(f"✅ *Status:* Approved by MIS ({approver_name})")
        else:
            lines.append("⏳ *Status:* Pending MIS Approval")

        return "\n".join(lines)

