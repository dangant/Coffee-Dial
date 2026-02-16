import operator

from sqlalchemy.orm import Session

from app.models.brew import Brew
from app.models.rating import Rating
from app.models.recommendation import RecommendationRule

OPS = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
}


def get_recommendations(db: Session, brew: Brew, rating: Rating) -> list[dict]:
    rules = db.query(RecommendationRule).all()
    results = []
    for rule in rules:
        value = getattr(rating, rule.condition_field, None)
        if value is None:
            value = getattr(brew, rule.condition_field, None)
        if value is None:
            continue
        op_func = OPS.get(rule.condition_operator)
        if not op_func:
            continue
        try:
            threshold = float(rule.condition_value)
        except ValueError:
            continue
        if op_func(value, threshold):
            results.append({
                "category": rule.category,
                "suggestion": rule.suggestion,
            })
    return results


def seed_rules(db: Session) -> None:
    """Seed default recommendation rules if none exist."""
    if db.query(RecommendationRule).count() > 0:
        return

    rules = [
        # Bitterness issues
        ("bitterness", ">=", "4", "Try a coarser grind setting to reduce bitterness", "grind"),
        ("bitterness", ">=", "4", "Lower your water temperature by 2-5°F to reduce over-extraction", "temperature"),
        ("bitterness", ">=", "4", "Reduce brew time by 15-30 seconds", "time"),
        # Sourness / acidity issues
        ("acidity", ">=", "4", "Try a finer grind to increase extraction and reduce sourness", "grind"),
        ("acidity", ">=", "4", "Increase water temperature by 2-5°F for better extraction", "temperature"),
        ("acidity", ">=", "4", "Extend brew time by 15-30 seconds to extract more sweetness", "time"),
        # Weak body
        ("body", "<=", "2", "Increase your coffee dose (bean amount) by 1-2 grams", "dose"),
        ("body", "<=", "2", "Try a finer grind for more body and mouthfeel", "grind"),
        ("body", "<=", "2", "Reduce water amount to increase concentration", "ratio"),
        # Low sweetness
        ("sweetness", "<=", "2", "Aim for the sweet spot: slightly finer grind or longer brew time", "grind"),
        ("sweetness", "<=", "2", "Try water at 200-205°F for optimal sweetness extraction", "temperature"),
        # Weak aroma
        ("aroma", "<=", "2", "Use fresher beans (within 2-4 weeks of roast date)", "beans"),
        ("aroma", "<=", "2", "Try blooming your coffee for 30-45 seconds before brewing", "technique"),
        # Low overall score
        ("overall_score", "<=", "4", "Consider trying a different brew method for this bean", "method"),
        ("overall_score", "<=", "4", "Adjust your coffee-to-water ratio closer to 1:16", "ratio"),
    ]

    for cond_field, cond_op, cond_val, suggestion, category in rules:
        db.add(RecommendationRule(
            condition_field=cond_field,
            condition_operator=cond_op,
            condition_value=cond_val,
            suggestion=suggestion,
            category=category,
        ))
    db.commit()
