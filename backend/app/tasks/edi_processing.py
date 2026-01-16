"""
Regula Health - EDI Processing Tasks
Background tasks for parsing and processing EDI 835 files
"""

from typing import Optional
from datetime import datetime
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from celery import Task

from app.tasks.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.services.edi_parser import edi_parser
from app.services.rate_engine import RateEngine
from app.models import Claim, Provider, Organization
from redis.asyncio import Redis

logger = structlog.get_logger()


class DatabaseTask(Task):
    """Base task with database session management"""
    _db: Optional[AsyncSession] = None
    _redis: Optional[Redis] = None
    
    @property
    def db(self) -> AsyncSession:
        if self._db is None:
            self._db = AsyncSessionLocal()
        return self._db
    
    @property
    def redis(self) -> Redis:
        if self._redis is None:
            self._redis = Redis.from_url("redis://localhost:6379/0")
        return self._redis


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    max_retries=3,
    default_retry_delay=60,
    name='app.tasks.edi_processing.process_edi_file'
)
def process_edi_file(
    self,
    file_content: str,
    provider_id: str,
    organization_id: str,
    file_name: str
) -> dict:
    """
    Background task to parse and process EDI 835 file
    
    Steps:
    1. Parse EDI file with EDI835Parser
    2. Lookup mandate rates for each claim
    3. Detect violations
    4. Insert into database (batch insert, 1000 at a time)
    5. Track progress (0%, 25%, 50%, 75%, 100%)
    6. Return summary statistics
    
    Args:
        file_content: EDI 835 file content as string
        provider_id: Provider UUID
        organization_id: Organization UUID
        file_name: Original filename
        
    Returns:
        Dict with processing results
    """
    import asyncio
    
    async def _process():
        try:
            # Update progress: 0% - Starting
            self.update_state(
                state='PROGRESS',
                meta={'current': 0, 'total': 100, 'status': 'Starting EDI parse...'}
            )
            
            # Step 1: Parse EDI file
            logger.info("parsing_edi_file", file_name=file_name)
            parsed_claims = await edi_parser.parse_file(file_content)
            
            if not parsed_claims:
                return {
                    'status': 'error',
                    'message': 'No claims found in EDI file',
                    'claims_processed': 0
                }
            
            # Update progress: 25% - Parsing complete
            self.update_state(
                state='PROGRESS',
                meta={'current': 25, 'total': 100, 'status': f'Parsed {len(parsed_claims)} claims'}
            )
            
            # Step 2: Get provider and rate engine
            async with AsyncSessionLocal() as db:
                from sqlalchemy import select
                
                stmt = select(Provider).where(Provider.id == provider_id)
                result = await db.execute(stmt)
                provider = result.scalar_one_or_none()
                
                if not provider:
                    return {
                        'status': 'error',
                        'message': 'Provider not found',
                        'claims_processed': 0
                    }
                
                redis = Redis.from_url("redis://localhost:6379/0")
                rate_engine = RateEngine(db, redis)
                
                # Update progress: 50% - Starting violation detection
                self.update_state(
                    state='PROGRESS',
                    meta={'current': 50, 'total': 100, 'status': 'Detecting violations...'}
                )
                
                # Step 3: Process claims in batches
                violations_count = 0
                claims_to_insert = []
                batch_size = 1000
                
                for idx, claim_data in enumerate(parsed_claims):
                    # Skip if no date of service
                    if not claim_data.get('dos'):
                        continue
                    
                    # Detect violation
                    violation_info = await rate_engine.detect_violation(
                        cpt_code=claim_data['cpt_code'],
                        paid_amount=claim_data['paid_amount'],
                        service_date=claim_data['dos'],
                        geo_region=provider.geo_region or 'upstate'
                    )
                    
                    # Only save if rate was found
                    if violation_info['mandate_rate'] is not None:
                        claim = Claim(
                            provider_id=provider.id,
                            claim_id=claim_data['claim_id'],
                            payer=claim_data['payer'],
                            payer_id=claim_data.get('payer_id'),
                            dos=claim_data['dos'],
                            cpt_code=claim_data['cpt_code'],
                            units=claim_data.get('units', 1),
                            billed_amount=claim_data.get('billed_amount'),
                            mandate_rate=violation_info['mandate_rate'],
                            paid_amount=claim_data['paid_amount'],
                            delta=violation_info['delta'],
                            is_violation=violation_info['is_violation'],
                            geo_adjustment_factor=violation_info['geo_adjustment_factor'],
                            edi_file_name=file_name
                        )
                        claims_to_insert.append(claim)
                        
                        if violation_info['is_violation']:
                            violations_count += 1
                    
                    # Batch insert every 1000 claims
                    if len(claims_to_insert) >= batch_size:
                        db.add_all(claims_to_insert)
                        await db.commit()
                        claims_to_insert = []
                        
                        # Update progress
                        progress = 50 + int((idx / len(parsed_claims)) * 40)
                        self.update_state(
                            state='PROGRESS',
                            meta={'current': progress, 'total': 100, 'status': f'Processed {idx}/{len(parsed_claims)} claims'}
                        )
                
                # Insert remaining claims
                if claims_to_insert:
                    db.add_all(claims_to_insert)
                    await db.commit()
                
                # Update progress: 90% - Database insertion complete
                self.update_state(
                    state='PROGRESS',
                    meta={'current': 90, 'total': 100, 'status': 'Finalizing...'}
                )
                
                await redis.aclose()
                
                # Step 4: Send notification if violations exceed threshold
                if violations_count > 10:
                    logger.warning(
                        "high_violation_count",
                        file_name=file_name,
                        violations=violations_count,
                        total_claims=len(parsed_claims)
                    )
                    # TODO: Send email notification
                
                # Complete
                result = {
                    'status': 'success',
                    'claims_processed': len(parsed_claims),
                    'violations_found': violations_count,
                    'file_name': file_name,
                    'processing_time': datetime.utcnow().isoformat()
                }
                
                logger.info(
                    "edi_processing_complete",
                    **result
                )
                
                return result
                
        except Exception as e:
            logger.error(
                "edi_processing_error",
                file_name=file_name,
                error=str(e)
            )
            
            # Retry on transient errors
            if 'timeout' in str(e).lower() or 'connection' in str(e).lower():
                raise self.retry(exc=e)
            
            return {
                'status': 'error',
                'message': str(e),
                'claims_processed': 0
            }
    
    # Run async function in sync context
    return asyncio.run(_process())


@celery_app.task(name='app.tasks.edi_processing.get_task_status')
def get_task_status(task_id: str) -> dict:
    """
    Get status of an EDI processing task
    
    Args:
        task_id: Celery task ID
        
    Returns:
        Task status information
    """
    task = celery_app.AsyncResult(task_id)
    
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'status': 'Task is waiting to be processed'
        }
    elif task.state == 'PROGRESS':
        response = {
            'state': task.state,
            'current': task.info.get('current', 0),
            'total': task.info.get('total', 100),
            'status': task.info.get('status', '')
        }
    elif task.state == 'SUCCESS':
        response = {
            'state': task.state,
            'result': task.result
        }
    else:
        # Error or other state
        response = {
            'state': task.state,
            'status': str(task.info)
        }
    
    return response
