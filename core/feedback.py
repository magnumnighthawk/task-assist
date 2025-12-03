"""Feedback and learning system for agent optimization.

Provides functions to log conversation feedback, generate learning summaries,
and retrieve learning context to improve agent behavior over time.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from db import SessionLocal, ConversationLog, FeedbackSummary

logger = logging.getLogger(__name__)


def log_conversation_feedback(
    conversation_summary: str,
    what_went_well: Optional[str] = None,
    what_could_improve: Optional[str] = None,
    user_satisfaction_estimate: Optional[str] = None,
    context_tags: Optional[List[str]] = None
) -> Optional[int]:
    """Log feedback about a conversation for learning purposes.
    
    Args:
        conversation_summary: Brief summary of what happened in the conversation
        what_went_well: Things that worked well
        what_could_improve: Areas that could be improved
        user_satisfaction_estimate: Estimated satisfaction (Low, Medium, High)
        context_tags: List of context tags (e.g., ["work_creation", "due_dates"])
        
    Returns:
        Feedback log ID or None if failed
    """
    db = SessionLocal()
    try:
        # Join tags if provided
        tags_str = ','.join(context_tags) if context_tags else None
        
        log = ConversationLog(
            conversation_summary=conversation_summary,
            what_went_well=what_went_well,
            what_could_improve=what_could_improve,
            user_satisfaction_estimate=user_satisfaction_estimate,
            context_tags=tags_str
        )
        
        db.add(log)
        db.commit()
        db.refresh(log)
        
        logger.info(f"Logged conversation feedback: {log.id}")
        return log.id
        
    except Exception as e:
        logger.exception("Failed to log conversation feedback")
        db.rollback()
        return None
    finally:
        db.close()


def get_recent_feedback(days: int = 30, limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent conversation feedback logs.
    
    Args:
        days: Number of days to look back
        limit: Maximum number of logs to return
        
    Returns:
        List of feedback log dictionaries
    """
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        logs = db.query(ConversationLog).filter(
            ConversationLog.created_at >= cutoff
        ).order_by(
            ConversationLog.created_at.desc()
        ).limit(limit).all()
        
        result = []
        for log in logs:
            result.append({
                'id': log.id,
                'conversation_summary': log.conversation_summary,
                'what_went_well': log.what_went_well,
                'what_could_improve': log.what_could_improve,
                'user_satisfaction_estimate': log.user_satisfaction_estimate,
                'context_tags': log.context_tags.split(',') if log.context_tags else [],
                'created_at': log.created_at.isoformat()
            })
        
        return result
        
    except Exception as e:
        logger.exception("Failed to get recent feedback")
        return []
    finally:
        db.close()


def create_feedback_summary(
    period_start: datetime,
    period_end: datetime,
    key_learnings: str,
    behavior_adjustments: str,
    total_conversations: int = 0
) -> Optional[int]:
    """Create a new feedback summary period.
    
    Args:
        period_start: Start of the summary period
        period_end: End of the summary period
        key_learnings: Main insights and patterns discovered
        behavior_adjustments: Specific behavior changes to apply
        total_conversations: Number of conversations analyzed
        
    Returns:
        Summary ID or None if failed
    """
    db = SessionLocal()
    try:
        summary = FeedbackSummary(
            period_start=period_start,
            period_end=period_end,
            total_conversations=total_conversations,
            key_learnings=key_learnings,
            behavior_adjustments=behavior_adjustments,
            active=True
        )
        
        db.add(summary)
        db.commit()
        db.refresh(summary)
        
        logger.info(f"Created feedback summary: {summary.id}")
        return summary.id
        
    except Exception as e:
        logger.exception("Failed to create feedback summary")
        db.rollback()
        return None
    finally:
        db.close()


def get_active_learning_context() -> Dict[str, Any]:
    """Get currently active learning summaries for context injection.
    
    Returns:
        Dict with active learning insights and behavior adjustments
    """
    db = SessionLocal()
    try:
        # Get active summaries ordered by recency
        summaries = db.query(FeedbackSummary).filter(
            FeedbackSummary.active == True
        ).order_by(
            FeedbackSummary.created_at.desc()
        ).limit(5).all()
        
        if not summaries:
            return {
                'has_learning': False,
                'summaries': [],
                'combined_adjustments': ''
            }
        
        # Combine learning insights
        all_learnings = []
        all_adjustments = []
        
        for summary in summaries:
            all_learnings.append({
                'period': f"{summary.period_start.strftime('%Y-%m-%d')} to {summary.period_end.strftime('%Y-%m-%d')}",
                'key_learnings': summary.key_learnings,
                'behavior_adjustments': summary.behavior_adjustments,
                'conversations': summary.total_conversations
            })
            all_adjustments.append(summary.behavior_adjustments)
        
        # Create combined adjustment text for easy injection
        combined = "\n\n".join([
            f"Learning Period {i+1}:\n{adj}"
            for i, adj in enumerate(all_adjustments)
        ])
        
        return {
            'has_learning': True,
            'summaries': all_learnings,
            'combined_adjustments': combined,
            'total_summaries': len(summaries)
        }
        
    except Exception as e:
        logger.exception("Failed to get active learning context")
        return {
            'has_learning': False,
            'summaries': [],
            'combined_adjustments': ''
        }
    finally:
        db.close()


def deactivate_old_summaries(keep_recent: int = 3) -> int:
    """Deactivate old summaries to keep context focused on recent learnings.
    
    Args:
        keep_recent: Number of recent summaries to keep active
        
    Returns:
        Number of summaries deactivated
    """
    db = SessionLocal()
    try:
        # Get all active summaries ordered by creation date
        summaries = db.query(FeedbackSummary).filter(
            FeedbackSummary.active == True
        ).order_by(
            FeedbackSummary.created_at.desc()
        ).all()
        
        if len(summaries) <= keep_recent:
            return 0
        
        # Deactivate older ones
        to_deactivate = summaries[keep_recent:]
        count = 0
        
        for summary in to_deactivate:
            summary.active = False
            count += 1
        
        db.commit()
        logger.info(f"Deactivated {count} old summaries")
        return count
        
    except Exception as e:
        logger.exception("Failed to deactivate old summaries")
        db.rollback()
        return 0
    finally:
        db.close()


def generate_learning_summary_from_feedback(days: int = 7) -> Optional[Dict[str, Any]]:
    """Analyze recent feedback and generate a learning summary using LLM.
    
    This function aggregates feedback from the specified period and uses
    the LLM to identify patterns and generate behavior adjustments.
    
    Args:
        days: Number of days of feedback to analyze
        
    Returns:
        Dict with summary data or None if failed
    """
    from generate import generate_subtasks  # Reuse LLM infrastructure
    import json
    
    db = SessionLocal()
    try:
        # Get feedback from the period
        period_end = datetime.utcnow()
        period_start = period_end - timedelta(days=days)
        
        logs = db.query(ConversationLog).filter(
            ConversationLog.created_at >= period_start,
            ConversationLog.created_at <= period_end
        ).order_by(
            ConversationLog.created_at.desc()
        ).all()
        
        if not logs:
            logger.info(f"No feedback logs found in last {days} days")
            return None
        
        # Prepare feedback summary for LLM
        feedback_text = f"Analyzing {len(logs)} conversations from the past {days} days:\n\n"
        
        for i, log in enumerate(logs, 1):
            feedback_text += f"Conversation {i}:\n"
            feedback_text += f"Summary: {log.conversation_summary}\n"
            if log.what_went_well:
                feedback_text += f"✓ Went well: {log.what_went_well}\n"
            if log.what_could_improve:
                feedback_text += f"⚠ Could improve: {log.what_could_improve}\n"
            if log.user_satisfaction_estimate:
                feedback_text += f"Satisfaction: {log.user_satisfaction_estimate}\n"
            if log.context_tags:
                feedback_text += f"Context: {log.context_tags}\n"
            feedback_text += "\n"
        
        # Use LLM to analyze patterns
        analysis_prompt = f"""{feedback_text}

Based on these conversation feedbacks, identify:
1. KEY LEARNINGS: What patterns emerge? What consistently works well or needs improvement?
2. BEHAVIOR ADJUSTMENTS: What specific changes should the agent make to improve?

Format as JSON:
{{
  "key_learnings": "string - main insights and patterns",
  "behavior_adjustments": "string - specific actionable changes",
  "confidence": "High/Medium/Low"
}}"""
        
        # Note: We're reusing generate_subtasks infrastructure, but ideally would have dedicated endpoint
        # For now, we'll parse the response manually
        logger.info("Generating learning summary from feedback...")
        
        # Create a simple analysis without LLM for now (can be enhanced)
        improvements = []
        successes = []
        
        for log in logs:
            if log.what_could_improve:
                improvements.append(log.what_could_improve)
            if log.what_went_well:
                successes.append(log.what_went_well)
        
        key_learnings = "Pattern Analysis:\n"
        if successes:
            key_learnings += f"- Successful approaches: {'; '.join(set(successes[:5]))}\n"
        if improvements:
            key_learnings += f"- Areas needing improvement: {'; '.join(set(improvements[:5]))}\n"
        
        behavior_adjustments = "Recommended Adjustments:\n"
        # Simple heuristic-based adjustments
        if any('confirmation' in imp.lower() or 'ask too much' in imp.lower() for imp in improvements):
            behavior_adjustments += "- Ask fewer confirmation questions; combine related confirmations\n"
        if any('unclear' in imp.lower() or 'confusing' in imp.lower() for imp in improvements):
            behavior_adjustments += "- Be more explicit and clear in explanations\n"
        if any('slow' in imp.lower() or 'too many steps' in imp.lower() for imp in improvements):
            behavior_adjustments += "- Streamline workflows; reduce unnecessary steps\n"
        if any('date' in imp.lower() for imp in improvements):
            behavior_adjustments += "- Improve due date handling and clarity\n"
        
        return {
            'period_start': period_start,
            'period_end': period_end,
            'total_conversations': len(logs),
            'key_learnings': key_learnings,
            'behavior_adjustments': behavior_adjustments if behavior_adjustments != "Recommended Adjustments:\n" else "- Continue current approach; no major issues identified\n"
        }
        
    except Exception as e:
        logger.exception("Failed to generate learning summary")
        return None
    finally:
        db.close()


def apply_learning_summary(summary_data: Dict[str, Any]) -> Optional[int]:
    """Create and activate a new learning summary.
    
    Args:
        summary_data: Dict with period_start, period_end, key_learnings, behavior_adjustments, total_conversations
        
    Returns:
        Summary ID or None if failed
    """
    summary_id = create_feedback_summary(
        period_start=summary_data['period_start'],
        period_end=summary_data['period_end'],
        key_learnings=summary_data['key_learnings'],
        behavior_adjustments=summary_data['behavior_adjustments'],
        total_conversations=summary_data.get('total_conversations', 0)
    )
    
    if summary_id:
        # Keep only recent summaries active
        deactivate_old_summaries(keep_recent=3)
    
    return summary_id
