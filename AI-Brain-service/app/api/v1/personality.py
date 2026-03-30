from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_personality_store, verify_api_key
from app.models.schemas import PersonalityConfig, PersonalityResponse
from app.services.personality_store import PersonalityStore

router = APIRouter(prefix="/personality", tags=["personality"], dependencies=[Depends(verify_api_key)])


class PersonalityCreateRequest(PersonalityConfig):
    personality_id: str = ""


@router.post("/", response_model=PersonalityResponse, status_code=201)
async def create_personality(
    body: PersonalityCreateRequest,
    store: PersonalityStore = Depends(get_personality_store),
) -> PersonalityResponse:
    if not body.personality_id:
        body.personality_id = str(uuid.uuid4())

    body.created_at = datetime.now(timezone.utc)
    body.updated_at = body.created_at

    config = PersonalityConfig(**body.model_dump())
    saved = await store.save(config)
    return PersonalityResponse(
        personality_id=saved.personality_id,
        name=saved.name,
        system_prompt=saved.system_prompt,
        tone=saved.tone,
        constraints=saved.constraints,
    )


@router.get("/{personality_id}", response_model=PersonalityResponse)
async def get_personality(
    personality_id: str,
    store: PersonalityStore = Depends(get_personality_store),
) -> PersonalityResponse:
    config = await store.get(personality_id)
    if not config:
        raise HTTPException(status_code=404, detail="Personality not found")
    return PersonalityResponse(
        personality_id=config.personality_id,
        name=config.name,
        system_prompt=config.system_prompt,
        tone=config.tone,
        constraints=config.constraints,
    )


@router.get("/user/{user_id}", response_model=list[PersonalityResponse])
async def list_user_personalities(
    user_id: str,
    store: PersonalityStore = Depends(get_personality_store),
) -> list[PersonalityResponse]:
    configs = await store.list_for_user(user_id)
    return [
        PersonalityResponse(
            personality_id=c.personality_id,
            name=c.name,
            system_prompt=c.system_prompt,
            tone=c.tone,
            constraints=c.constraints,
        )
        for c in configs
    ]


@router.delete("/{personality_id}", status_code=204)
async def delete_personality(
    personality_id: str,
    store: PersonalityStore = Depends(get_personality_store),
) -> None:
    deleted = await store.delete(personality_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Personality not found")
