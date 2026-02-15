"""Pydantic models for weather module request/response validation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CurrentWeatherRequest(BaseModel):
    location: str
    units: str = "metric"


class ForecastRequest(BaseModel):
    location: str
    days: int = Field(default=7, ge=1, le=16)
    units: str = "metric"


class HourlyRequest(BaseModel):
    location: str
    hours: int = Field(default=24, ge=1, le=168)
    units: str = "metric"


class AlertsRequest(BaseModel):
    location: str
