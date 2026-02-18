from sqlalchemy.orm import Session

from app.models.lookups import BrewDevice, FlavorNote, Grinder


def list_flavor_notes(db: Session) -> list[FlavorNote]:
    return db.query(FlavorNote).order_by(FlavorNote.name).all()


def add_flavor_note(db: Session, name: str) -> FlavorNote:
    existing = db.query(FlavorNote).filter(FlavorNote.name == name).first()
    if existing:
        return existing
    note = FlavorNote(name=name)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def list_brew_devices(db: Session) -> list[BrewDevice]:
    return db.query(BrewDevice).order_by(BrewDevice.name).all()


def add_brew_device(db: Session, name: str) -> BrewDevice:
    existing = db.query(BrewDevice).filter(BrewDevice.name == name).first()
    if existing:
        return existing
    device = BrewDevice(name=name)
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def list_grinders(db: Session) -> list[Grinder]:
    return db.query(Grinder).order_by(Grinder.name).all()


def add_grinder(db: Session, name: str) -> Grinder:
    existing = db.query(Grinder).filter(Grinder.name == name).first()
    if existing:
        return existing
    grinder = Grinder(name=name)
    db.add(grinder)
    db.commit()
    db.refresh(grinder)
    return grinder


def seed_lookups(db: Session) -> None:
    """Seed default flavor notes and brew devices if none exist."""
    if db.query(FlavorNote).count() == 0:
        defaults = [
            "Berry", "Blackberry", "Blueberry", "Caramel", "Cherry",
            "Chocolate", "Cinnamon", "Citrus", "Cocoa", "Coconut",
            "Cranberry", "Floral", "Grape", "Green Apple", "Hazelnut",
            "Honey", "Jasmine", "Lemon", "Mango", "Maple",
            "Molasses", "Nougat", "Nutty", "Orange", "Peach",
            "Peanut", "Plum", "Raspberry", "Stone Fruit", "Strawberry",
            "Sugarcane", "Toffee", "Tropical", "Vanilla", "Winey",
        ]
        for name in defaults:
            db.add(FlavorNote(name=name))
        db.commit()

    if db.query(Grinder).count() == 0:
        defaults = [
            "1Zpresso J-Max", "1Zpresso JX-Pro", "1Zpresso K-Max", "1Zpresso K-Plus",
            "1Zpresso Q2", "Baratza Encore", "Baratza Sette 270",
            "Baratza Virtuoso+", "Comandante C40", "Fellow Ode",
            "Hario Skerton", "JavaPresse Manual", "Kinu M47",
            "Niche Zero", "Porlex Mini", "Timemore C2",
            "Timemore Chestnut X",
        ]
        for name in defaults:
            db.add(Grinder(name=name))
        db.commit()

    if db.query(BrewDevice).count() == 0:
        defaults = [
            "Chemex", "Flair Espresso", "V60", "Kalita Wave",
            "AeroPress", "French Press", "Moka Pot", "Clever Dripper",
            "Origami", "Fellow Stagg", "Siphon", "Breville Barista Express",
        ]
        for name in defaults:
            db.add(BrewDevice(name=name))
        db.commit()
