"""Pydantic models for interview scheduling system"""

from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional
from datetime import datetime
import re


class SchedulingRequest(BaseModel):
    """Request model for initiating interview scheduling"""
    applicant_name: str = Field(..., min_length=1, max_length=255)
    applicant_phone: str = Field(..., min_length=10, max_length=20)
    company_name: str = Field(..., min_length=1, max_length=255)
    position: str = Field(..., min_length=1, max_length=255)
    job_id: str = Field(..., min_length=1, max_length=100)           
    candidate_id: int = Field(..., gt=0)    
    location: str = Field(..., min_length=1, max_length=255)
    interview_type: str = Field(..., min_length=1, max_length=50)     
    meeting_link: str = Field(default="", max_length=500)             
    slots: Dict[str, List[str]] = Field(..., description="Available interview slots by date")
    
    @validator('applicant_phone')
    def validate_phone(cls, v):
        """Validate phone number format"""
        # Remove common separators
        cleaned = re.sub(r'[\s\-\(\)\.]', '', v)
        
        # Check if it starts with + and has 10+ digits
        if not re.match(r'^\+?\d{10,}$', cleaned):
            raise ValueError('Phone number must be in E.164 format (e.g., +11234567890)')
        
        # Ensure it starts with +
        if not cleaned.startswith('+'):
            cleaned = '+' + cleaned
        
        return cleaned
    
    @validator('slots')
    def validate_slots(cls, v):
        """Validate slots dictionary is not empty"""
        if not v:
            raise ValueError('At least one interview slot must be provided')
        
        for date, times in v.items():
            if not times:
                raise ValueError(f'No time slots provided for {date}')
        
        return v


class SchedulingResponse(BaseModel):
    """Response model for scheduling initiation"""
    session_id: str
    status: str
    message: str


class SchedulingStatusResponse(BaseModel):
    """Response model for checking scheduling status"""
    session_id: str
    status: str
    applicant_name: str
    company_name: str
    position: str
    selected_date: Optional[str] = None
    selected_time: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class LLMAnalysis(BaseModel):
    """Analysis portion of LLM response"""
    intent: str
    selected_date: Optional[str] = None
    selected_time: Optional[str] = None
    is_valid_selection: bool = False
    confidence: str
    requires_confirmation: bool = False


class LLMResponse(BaseModel):
    """Complete LLM response structure"""
    analysis: LLMAnalysis
    response_message: str
    action: str
    session_status: str


class ConversationMessage(BaseModel):
    """Single message in conversation history"""
    role: str  # 'assistant' or 'applicant'
    message: str
    timestamp: str


class SessionData(BaseModel):
    """Complete session data from database"""
    session_id: str
    applicant_name: str
    applicant_phone: str
    company_name: str
    position: str
    job_id: str              
    candidate_id: int      
    location: str    
    interview_type: str              
    meeting_link: str   
    available_slots: dict
    conversation_history: List[dict]
    selected_date: Optional[str] = None
    selected_time: Optional[str] = None
    status: str
