#python imports

#third-party imports

#project imports

SLOT_ALIASES = {
    "employment.company": "employment.current_company",
    "employment.current_company": "employment.current_company",
    "job.company": "employment.current_company",
    "location.city": "location.current_city",
    "location.current_city": "location.current_city",
    "home.city": "location.current_city",
    "pet.dog": "pet.dog.name",
    "pet.dog.name": "pet.dog.name",
}


def canonical_slot(key: str) -> str:
    normalized_key = key.strip().lower()
    return SLOT_ALIASES.get(normalized_key, normalized_key)
