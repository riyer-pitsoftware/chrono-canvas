"""Neo-Mumbai-Noir data models migrated to PostgreSQL."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from chronocanvas.db.base import Base, TimestampMixin, UUIDMixin


class NeoStory(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "neo_stories"

    title: Mapped[str] = mapped_column(String(500), index=True)
    content: Mapped[str | None] = mapped_column(Text)
    llm_model: Mapped[str | None] = mapped_column(String(255))

    characters: Mapped[list["NeoCharacter"]] = relationship(back_populates="story")


class NeoCharacter(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "neo_characters"
    __table_args__ = (UniqueConstraint("story_id", "slug", name="uq_neo_characters_story_slug"),)

    story_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("neo_stories.id"))
    name: Mapped[str] = mapped_column(String(255), index=True)
    slug: Mapped[str] = mapped_column(String(255), index=True)
    age: Mapped[str | None] = mapped_column(String(100))
    ethnicity: Mapped[str | None] = mapped_column(String(255))
    gender: Mapped[str | None] = mapped_column(String(100))
    facial_features: Mapped[list | None] = mapped_column(JSONB, default=list)
    clothing: Mapped[str | None] = mapped_column(Text)
    key_scenes: Mapped[list | None] = mapped_column(JSONB, default=list)
    emotions: Mapped[list | None] = mapped_column(JSONB, default=list)

    story: Mapped["NeoStory"] = relationship(back_populates="characters")
    scenes: Mapped[list["NeoScene"]] = relationship(back_populates="character")
    images: Mapped[list["NeoImage"]] = relationship(back_populates="character")


class NeoScene(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "neo_scenes"
    __table_args__ = (
        UniqueConstraint("character_id", "scene_key", name="uq_neo_scenes_character_key"),
    )

    character_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("neo_characters.id"))
    scene_key: Mapped[str] = mapped_column(String(255))
    scene_name: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)

    character: Mapped["NeoCharacter"] = relationship(back_populates="scenes")
    images: Mapped[list["NeoImage"]] = relationship(back_populates="scene")


class NeoImage(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "neo_images"

    character_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("neo_characters.id"))
    scene_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("neo_scenes.id"))
    image_type: Mapped[str | None] = mapped_column(String(100))
    file_path: Mapped[str] = mapped_column(String(500), unique=True)
    file_name: Mapped[str | None] = mapped_column(String(255))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str | None] = mapped_column(String(255))
    photographer: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(500))

    character: Mapped["NeoCharacter | None"] = relationship(back_populates="images")
    scene: Mapped["NeoScene | None"] = relationship(back_populates="images")


class NeoFaceSwap(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "neo_face_swaps"

    source_image_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("neo_images.id"))
    target_image_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("neo_images.id"))
    result_image_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("neo_images.id"))
    status: Mapped[str] = mapped_column(String(50), default="pending")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    source_image: Mapped["NeoImage"] = relationship(foreign_keys=[source_image_id])
    target_image: Mapped["NeoImage"] = relationship(foreign_keys=[target_image_id])
    result_image: Mapped["NeoImage | None"] = relationship(foreign_keys=[result_image_id])
