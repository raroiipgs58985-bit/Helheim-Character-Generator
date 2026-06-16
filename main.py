from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass, field
import random
import re


DATA_DIR = Path(__file__).parent / "data"

MAIN_STATS = ["НС", "НР", "СЛ", "ВН", "ЛВ", "ИН", "СВ", "ВС", "ОЩ"]
BONUS_NAMES = {
    "НС": "БНС",
    "НР": "БНР",
    "СЛ": "БСЛ",
    "ВН": "БВН",
    "ЛВ": "БЛВ",
    "ИН": "БИН",
    "СВ": "БСВ",
    "ВС": "БВС",
    "ОЩ": "БОЩ",
}


@dataclass
class Character:
    name: str = ""
    template_name: str = ""
    origin_name: str = ""
    specialty_name: str = ""

    stats: dict[str, int] = field(default_factory=dict)
    size: int = 0
    wound_bonus: int = 0

    armor_points: str = "0/0/0/0"
    madness: str = "0"
    fate: str = "0"

    skills: dict[str, int] = field(default_factory=dict)
    talents: list[str] = field(default_factory=list)
    traits: list[str] = field(default_factory=list)

    implants: list[str] = field(default_factory=list)
    equipment: list[str] = field(default_factory=list)
    notes: str = ""

    starting_xp: int = 1000
    xp_refund: int = 0
    spent_xp: int = 0


def read_blocks(path: Path) -> dict[str, dict[str, str]]:
    """
    Читает txt-базу формата:

    [Название]
    key=value
    key=value

    Возвращает:
    {
        "Название": {"key": "value"}
    }
    """
    blocks: dict[str, dict[str, str]] = {}
    current: str | None = None

    if not path.exists():
        print(f"Внимание: файл не найден: {path}")
        return blocks

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip()
            blocks[current] = {}
            continue

        if current and "=" in line:
            key, value = line.split("=", 1)
            blocks[current][key.strip()] = value.strip()

    return blocks


def parse_int(value: str | None, default: int = 0) -> int:
    if value is None:
        return default
    match = re.search(r"-?\d+", str(value))
    return int(match.group(0)) if match else default


def parse_stat_modifiers(text: str | None) -> dict[str, int]:
    """
    Формат:
    НС +5; НР +10; ОЩ -5
    """
    result = {s: 0 for s in MAIN_STATS}
    if not text:
        return result

    parts = [p.strip() for p in text.split(";") if p.strip()]
    for part in parts:
        match = re.match(r"^(НС|НР|СЛ|ВН|ЛВ|ИН|СВ|ВС|ОЩ)\s*([+-]?\d+)", part)
        if match:
            stat, value = match.groups()
            result[stat] += int(value)

    return result


def parse_base_stats(block: dict[str, str]) -> dict[str, int]:
    """
    Поддерживает два варианта:
    base_stats=НС 25; НР 25...
    или отдельные поля НС=25, НР=25...
    """
    stats = {s: 0 for s in MAIN_STATS}

    if "base_stats" in block:
        for part in block["base_stats"].split(";"):
            match = re.match(r"^\s*(НС|НР|СЛ|ВН|ЛВ|ИН|СВ|ВС|ОЩ)\s*=?\s*(-?\d+)", part.strip())
            if match:
                stat, value = match.groups()
                stats[stat] = int(value)

    for stat in MAIN_STATS:
        if stat in block:
            stats[stat] = parse_int(block[stat])

    return stats


def split_list(text: str | None) -> list[str]:
    if not text:
        return []
    return [x.strip() for x in text.split(";") if x.strip()]


def normalize_skill_name(skill: str) -> tuple[str, int]:
    """
    Возвращает:
    ("Первая помощь", 10)

    Если бонуса нет:
    ("Первая помощь", 0)

    Работает с:
    Первая помощь +10
    Общие знания (Армия) +10
    """
    skill = skill.strip()
    match = re.match(r"^(.*?)(?:\s+([+-]\d+))?$", skill)
    if not match:
        return skill, 0

    name = match.group(1).strip()
    bonus = int(match.group(2)) if match.group(2) else 0
    return name, bonus


def add_skills(char: Character, skills: list[str]) -> None:
    """
    Правило:
    - Первое получение навыка без бонуса = +0
    - Повторное получение навыка без бонуса = +5
    - Получение навыка с бонусом = прибавить указанный бонус
    """
    for raw in skills:
        name, bonus = normalize_skill_name(raw)
        if not name:
            continue

        if name not in char.skills:
            char.skills[name] = bonus
        else:
            char.skills[name] += bonus if bonus else 5


def add_talents(char: Character, talents: list[str], talents_db: dict[str, dict[str, str]]) -> None:
    """
    Повторный талант:
    - если repeatable=true, оставляем повтор
    - иначе убираем повтор и возвращаем +25 опыта
    """
    for talent in talents:
        name = talent.strip()
        if not name:
            continue

        db = talents_db.get(name, {})
        repeatable = db.get("repeatable", "false").lower() == "true"

        if repeatable:
            char.talents.append(name)
            continue

        if name in char.talents:
            char.xp_refund += 25
        else:
            char.talents.append(name)


def add_traits(char: Character, traits: list[str]) -> None:
    for trait in traits:
        trait = trait.strip()
        if trait and trait not in char.traits:
            char.traits.append(trait)


def add_equipment(char: Character, equipment: list[str]) -> None:
    for item in equipment:
        item = item.strip()
        if item:
            char.equipment.append(item)


def characteristic_bonus(value: int) -> int:
    return value // 10


def calc_bonuses(stats: dict[str, int]) -> dict[str, int]:
    return {BONUS_NAMES[s]: characteristic_bonus(stats.get(s, 0)) for s in MAIN_STATS}


def calc_movement(char: Character) -> str:
    bonuses = calc_bonuses(char.stats)
    base = bonuses["БЛВ"] + char.size
    return f"{base}/{base * 2}/{base * 3}/{base * 6}"


def calc_endurance_bonus(char: Character) -> int:
    return characteristic_bonus(char.stats.get("ВН", 0))


def calc_wounds(char: Character) -> int:
    bonuses = calc_bonuses(char.stats)
    return char.wound_bonus + (bonuses["БВН"] + bonuses["БСВ"]) * 2


def choose_from_list(title: str, options: list[str]) -> str:
    print(f"\n{title}")
    for i, option in enumerate(options, start=1):
        print(f"{i}. {option}")

    while True:
        raw = input("> ").strip()
        if raw.isdigit():
            index = int(raw)
            if 1 <= index <= len(options):
                return options[index - 1]
        print("Введите номер из списка.")


def input_int(prompt: str, default: int = 0) -> int:
    raw = input(prompt).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print("Не число, поставлено значение по умолчанию.")
        return default


def distribute_stats(base_stats: dict[str, int], points: int, max_add: int) -> dict[str, int]:
    print("\nРаспределение характеристик")
    print(f"Доступно очков: {points}")
    print(f"Максимум в одну характеристику: {max_add}")

    additions = {s: 0 for s in MAIN_STATS}

    while True:
        remaining = points - sum(additions.values())
        print(f"\nОсталось очков: {remaining}")
        for stat in MAIN_STATS:
            print(f"{stat}: база {base_stats.get(stat, 0)} + {additions[stat]} = {base_stats.get(stat, 0) + additions[stat]}")

        if remaining == 0:
            break

        stat = input("\nКуда добавить очки? Введите НС/НР/СЛ/ВН/ЛВ/ИН/СВ/ВС/ОЩ: ").strip().upper()
        if stat not in MAIN_STATS:
            print("Нет такой характеристики.")
            continue

        amount = input_int(f"Сколько добавить в {stat}? ", 0)

        if amount <= 0:
            print("Нужно положительное число.")
            continue

        if additions[stat] + amount > max_add:
            print(f"В одну характеристику нельзя добавить больше {max_add}.")
            continue

        if amount > remaining:
            print("Столько очков не осталось.")
            continue

        additions[stat] += amount

    return {s: base_stats.get(s, 0) + additions[s] for s in MAIN_STATS}


def random_stats(base_stats: dict[str, int]) -> dict[str, int]:
    print("\nСлучайная генерация: на каждую характеристику бросается 2к10.")
    result = {}
    for stat in MAIN_STATS:
        roll = random.randint(1, 10) + random.randint(1, 10)
        result[stat] = base_stats.get(stat, 0) + roll
        print(f"{stat}: база {base_stats.get(stat, 0)} + бросок {roll} = {result[stat]}")

    print("\nПерераспределение пока сделайте вручную в итоговой карточке, если нужно.")
    return result


def apply_block(char: Character, block: dict[str, str], talents_db: dict[str, dict[str, str]]) -> None:
    stat_mods = parse_stat_modifiers(block.get("stat_modifiers"))
    for stat, value in stat_mods.items():
        char.stats[stat] = char.stats.get(stat, 0) + value

    char.size += parse_int(block.get("size"), 0)
    char.wound_bonus += parse_int(block.get("wound_bonus"), 0)

    add_skills(char, split_list(block.get("skills")) or split_list(block.get("starting_skills")))
    add_talents(char, split_list(block.get("talents")) or split_list(block.get("starting_talents")), talents_db)
    add_traits(char, split_list(block.get("traits")))
    add_equipment(char, split_list(block.get("equipment")) or split_list(block.get("starting_equipment")))


def generate_card(char: Character) -> str:
    bonuses = calc_bonuses(char.stats)
    remaining_xp = char.starting_xp + char.xp_refund - char.spent_xp

    lines = []
    lines.append("=" * 36)
    lines.append(char.name.upper() if char.name else "ПЕРСОНАЖ")
    lines.append("=" * 36)
    lines.append("")
    lines.append(f"Раса: {char.template_name}")
    lines.append(f"Родной мир / Природа Искина: {char.origin_name}")
    lines.append(f"Специальность: {char.specialty_name}")
    lines.append("")
    lines.append("ХАРАКТЕРИСТИКИ")
    for stat in MAIN_STATS:
        bonus_name = BONUS_NAMES[stat]
        lines.append(f"{stat}: {char.stats.get(stat, 0)} ({bonus_name} {bonuses[bonus_name]})")

    lines.append("")
    lines.append("ПРОИЗВОДНЫЕ")
    lines.append(f"Движение: {calc_movement(char)}")
    lines.append(f"ОБ: {char.armor_points}")
    lines.append(f"БВ: {calc_endurance_bonus(char)}")
    lines.append(f"Раны: {calc_wounds(char)}")
    lines.append(f"Очки безумия: {char.madness}")
    lines.append(f"Очки судьбы: {char.fate}")
    lines.append("")
    lines.append("ОПЫТ")
    lines.append(f"Стартовый опыт: {char.starting_xp}")
    lines.append(f"Компенсация за дубли талантов: {char.xp_refund}")
    lines.append(f"Потрачено: {char.spent_xp}")
    lines.append(f"Остаток: {remaining_xp}")

    lines.append("")
    lines.append("НАВЫКИ")
    if char.skills:
        for name in sorted(char.skills):
            value = char.skills[name]
            suffix = f" +{value}" if value else ""
            lines.append(f"- {name}{suffix}")
    else:
        lines.append("-")

    lines.append("")
    lines.append("ТАЛАНТЫ")
    if char.talents:
        for talent in char.talents:
            lines.append(f"- {talent}")
    else:
        lines.append("-")

    lines.append("")
    lines.append("ОСОБЕННОСТИ")
    if char.traits:
        for trait in char.traits:
            lines.append(f"- {trait}")
    else:
        lines.append("-")

    lines.append("")
    lines.append("ИМПЛАНТЫ")
    if char.implants:
        for implant in char.implants:
            lines.append(f"- {implant}")
    else:
        lines.append("-")

    lines.append("")
    lines.append("СНАРЯЖЕНИЕ")
    if char.equipment:
        for item in char.equipment:
            lines.append(f"- {item}")
    else:
        lines.append("-")

    if char.notes:
        lines.append("")
        lines.append("ПРИМЕЧАНИЕ")
        lines.append(char.notes)

    return "\n".join(lines)


def main() -> None:
    templates = read_blocks(DATA_DIR / "templates.txt")
    homeworlds = read_blocks(DATA_DIR / "homeworlds.txt")
    ai_natures = read_blocks(DATA_DIR / "ai_natures.txt")
    talents_db = read_blocks(DATA_DIR / "talents.txt")

    specialty_files = [
        DATA_DIR / "specialties_soldiers.txt",
        DATA_DIR / "specialties_officer_support.txt",
        DATA_DIR / "specialties_civilian.txt",
    ]

    specialties = {}
    for file in specialty_files:
        specialties.update(read_blocks(file))

    char = Character()
    char.name = input("Имя персонажа: ").strip() or "Безымянный"

    template_name = choose_from_list("Выберите расу/шаблон:", list(templates.keys()))
    template = templates[template_name]
    char.template_name = template_name

    base_stats = parse_base_stats(template)
    char.size += parse_int(template.get("size"), 0)
    char.wound_bonus += parse_int(template.get("wound_bonus"), 0)
    add_skills(char, split_list(template.get("skills")) or split_list(template.get("starting_skills")))
    add_talents(char, split_list(template.get("talents")) or split_list(template.get("starting_talents")), talents_db)
    add_traits(char, split_list(template.get("traits")))
    add_equipment(char, split_list(template.get("equipment")) or split_list(template.get("starting_equipment")))

    points = parse_int(template.get("stat_points_planned"), 100)
    max_add = parse_int(template.get("stat_max_add"), 20)

    mode = choose_from_list("Выберите способ характеристик:", ["Плановый", "Случайный 2к10"])
    if mode == "Плановый":
        char.stats = distribute_stats(base_stats, points, max_add)
    else:
        char.stats = random_stats(base_stats)

    if template.get("type", "").lower() == "synthetic" or template_name.lower() == "искин":
        origin_name = choose_from_list("Выберите природу Искина:", list(ai_natures.keys()))
        origin = ai_natures[origin_name]
    else:
        origin_name = choose_from_list("Выберите родной мир:", list(homeworlds.keys()))
        origin = homeworlds[origin_name]

    char.origin_name = origin_name
    apply_block(char, origin, talents_db)

    specialty_name = choose_from_list("Выберите специальность:", list(specialties.keys()))
    specialty = specialties[specialty_name]
    char.specialty_name = specialty_name

    specialty_cost = parse_int(specialty.get("cost"), 0)
    char.spent_xp += specialty_cost
    apply_block(char, specialty, talents_db)

    char.armor_points = input("ОБ вручную, например 3/4/3/3: ").strip() or "0/0/0/0"
    char.madness = input("Очки безумия: ").strip() or "0"
    char.fate = input("Очки судьбы: ").strip() or "0"

    raw_implants = input("Импланты через ; или пусто: ").strip()
    char.implants = split_list(raw_implants)

    char.notes = input("Примечание или пусто: ").strip()

    card = generate_card(char)

    print("\n" + card)

    out = Path(__file__).parent / f"{char.name.replace(' ', '_')}_card.txt"
    out.write_text(card, encoding="utf-8")
    print(f"\nКарточка сохранена: {out}")


if __name__ == "__main__":
    main()
