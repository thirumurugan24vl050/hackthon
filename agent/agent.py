"""
HYDRO MIND — AI Agent
Responds to user queries deterministically using tools and enforces safety constraints.
"""
from agent.tools import get_weather, get_reservoir_status, get_water_quality, get_alerts, get_recent_news
import os

class HydroAgent:
    def __init__(self):
        self.provider = os.getenv("AI_PROVIDER") # If unset, uses deterministic fallback
    
    def process_query(self, user_query: str) -> str:
        """Processes a query with strict safety constraints."""
        query_lower = user_query.lower()
        
        # Rule: Drinking Water Safety Refusal
        if any(word in query_lower for word in ["drink", "drinking", "safe", "potable"]):
            wq = get_water_quality()
            return (
                "The system cannot certify drinking-water safety. Current observations "
                f"indicate [WQI Status: {wq.get('status')}]. Official laboratory testing and "
                "applicable regulatory standards are required."
            )
            
        if any(word in query_lower for word in ["news", "update", "latest"]):
            news = get_recent_news()
            response = "RECENT UPDATES\n"
            for i, item in enumerate(news, 1):
                cat = item.get('category') or 'GENERAL'
                ver = item.get('verification_status') or 'UNCORROBORATED'
                response += f"{i}. Source: {item['source_domain']} / Publisher: {item['publisher']} / Time: {item['time']} / Category: {cat} / Verification: {ver} / Title: {item['title']}\n"
            
            alerts = get_alerts()
            response += "\nCORROBORATION\nCurrent HYDRO MIND data:\n"
            if alerts:
                for alert in alerts:
                    response += f"- [ALERT] {alert['severity']}: {alert['message']}\n"
            else:
                response += "- No active alerts corroborating news events.\n"
                
            return response
            
        if any(word in query_lower for word in ["weather", "rain", "temperature", "wind"]):
            weather = get_weather()
            if weather.get("status") == "LIVE":
                return (
                    f"Weather Status: LIVE at {weather.get('timestamp')}\n"
                    f"Temperature: {weather.get('temperature_2m')}\n"
                    f"Precipitation: {weather.get('precipitation')}\n"
                    f"Wind Speed: {weather.get('wind_speed_10m')}\n"
                )
            return "Weather Status: UNAVAILABLE"
            
        # Default deterministic response
        return "I am the HYDRO MIND AI Agent. I can provide recent updates on weather, news, alerts, and safety information based solely on verified telemetry."

def run_agent_test():
    agent = HydroAgent()
    print("User: Is the water safe to drink?")
    print("Agent:", agent.process_query("Is the water safe to drink?"))
    print("\nUser: What is the latest news?")
    print("Agent:\n" + agent.process_query("What is the latest news?"))

if __name__ == "__main__":
    run_agent_test()
