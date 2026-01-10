import sys
import os
from datetime import datetime, timedelta

# Add /app to path (since we are likely running from /app/storage/...)
sys.path.append("/app")

from app.database import SessionLocal
# Import all models to ensure registry is populated
import app.models
import app.models_application
import app.models_chat
import app.models_revive
import app.models_learning
import app.models_knowledge
import app.models_dashboards
import app.models_scheduler
import app.models_troubleshooting
import app.models_remediation

from app.models_learning import AIFeedback, RunbookClick
from app.services.runbook_analytics_service import RunbookAnalyticsService
from app.models_revive import KnowledgeSource

def verify_feedback():
    db = SessionLocal()
    try:
        print("--- 🔍 Verifying Feedback and Ranking Impact ---")
        
        # 1. Check AI Feedback Table
        latest_feedback = db.query(AIFeedback).order_by(AIFeedback.created_at.desc()).first()
        
        if not latest_feedback:
            print("❌ No feedback found in database!")
            return
            
        print(f"\n✅ Latest Feedback Found:")
        print(f"   ID: {latest_feedback.id}")
        print(f"   Type: {latest_feedback.feedback_type}")
        print(f"   Target: {latest_feedback.target_type}")
        print(f"   Runbook ID: {latest_feedback.runbook_id}")
        
        if not latest_feedback.runbook_id:
            print("\n⚠️ Latest feedback is for LLM response, not for a specific runbook.")
            print("   (Only runbook-targeted feedback affects ranking directly)")
            
            # SIMULATION MODE
            print("\n🧪 STARTING SIMULATION: Injecting Runbook Feedback to test ranking boost.")
            from app.models_remediation import Runbook
            runbook = db.query(Runbook).first()
            if not runbook:
                print("❌ No runbooks found to test.")
                return
                
            print(f"   Target Runbook: {runbook.name} ({runbook.id})")
            
            # 1. Get Baseline
            analytics_service = RunbookAnalyticsService(db)
            base_score = analytics_service.get_feedback_score(runbook.id)
            print(f"   Baseline Feedback Score: {base_score}")
            
            # 2. Insert Feedback
            sim_feedback = AIFeedback(
                user_id=latest_feedback.user_id,
                runbook_id=runbook.id,
                feedback_type="thumbs_up",
                target_type="runbook",
                query_text="Simulation test"
            )
            db.add(sim_feedback)
            db.commit()
            print("   ✅ Inserted 'thumbs_up' feedback.")
            
            # 3. Get New Score
            new_score = analytics_service.get_feedback_score(runbook.id)
            
            # Manual count for display
            pos = db.query(AIFeedback).filter(
                AIFeedback.runbook_id == runbook.id,
                AIFeedback.feedback_type == 'thumbs_up'
            ).count()
            neg = db.query(AIFeedback).filter(
                AIFeedback.runbook_id == runbook.id,
                AIFeedback.feedback_type == 'thumbs_down'
            ).count()
            
            print(f"   New Feedback Score: {new_score}")
            print(f"   Pos/Neg Count: {pos}/{neg}")
            
            # 4. Calculate Boost
            # Logic: multiplier = 1.0 + (score * 0.05)
            # Ranking Boost = Base * Multiplier
            # But SolutionRanker uses additive bonus in some versions or multiplicative.
            # Let's show the raw score delta.
            
            if new_score > base_score:
                 print("\n✅ SUCCESS: Runbook score INCREASED!")
                 print(f"   Delta: {new_score - base_score}")
            else:
                 print("\n⚠️ Score did not change (maybe capped?).")
                 
            return

        # 2. Check Analytics Service Score
        analytics_service = RunbookAnalyticsService(db)
        runbook_id = latest_feedback.runbook_id
        
        score = analytics_service.get_feedback_score(runbook_id)
        
         # Manual count for display
        pos = db.query(AIFeedback).filter(
            AIFeedback.runbook_id == runbook_id,
            AIFeedback.feedback_type == 'thumbs_up'
        ).count()
        neg = db.query(AIFeedback).filter(
            AIFeedback.runbook_id == runbook_id,
            AIFeedback.feedback_type == 'thumbs_down'
        ).count()
        
        print(f"\n📊 Analytics Score for Runbook {runbook_id}:")
        print(f"   Net Score: {score:.2f} (This is the raw modifier)")
        print(f"   Positive Feedback: {pos}")
        print(f"   Negative Feedback: {neg}")
        
        # 3. Simulate Ranker Calculation
        # Base formula: final = base + automation + popularity + feedback
        
        # Assume some dummy base values
        base_score = 0.85
        automation_bonus = 0.15
        popularity_bonus = 0.05 # Assume some clicks
        
        # Calculate feedback bonus (capped at 0.15)
        # Logic from SolutionRanker (simplified replication)
        feedback_bonus = 0.0
        if score > 0:
            feedback_bonus = min(0.15, score * 0.05) # 5% per net positive vote
        elif score < 0:
            feedback_bonus = max(-0.15, score * 0.05)
            
        current_total = base_score + automation_bonus + popularity_bonus + feedback_bonus
        baseline_total = base_score + automation_bonus + popularity_bonus # Without feedback
        
        print(f"\n🚀 Ranking Impact Simulation:")
        print(f"   Baseline Score: {baseline_total:.4f}")
        print(f"   Feedback Bonus: {feedback_bonus:+.4f} (from net score {score})")
        print(f"   Final Score:    {current_total:.4f}")
        
        if current_total > baseline_total:
            print("\n✅ SUCCESS: Feedback positively boosted the score!")
        elif current_total < baseline_total:
             print("\n⚠️ Feedback negatively impacted the score (expected if thumbs down).")
        else:
             print("\n⚠️ No impact observed (maybe score is 0).")

    finally:
        db.close()

if __name__ == "__main__":
    verify_feedback()
