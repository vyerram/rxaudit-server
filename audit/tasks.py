from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
import logging
import signal

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="audit.process_zip_file")
def process_zip_file_task(
    self, file_path, process_log_id, obj_id, pharmacy_id, is_resubmission=False, process_folder=None
):
    """
    Celery task to process ZIP file asynchronously.

    Args:
        file_path: Path to the uploaded ZIP file (temporary location)
        process_log_id: ID of the ProcessLogHdr object
        obj_id: ID of the object (same as process_log in most cases)
        pharmacy_id: ID of the pharmacy
        is_resubmission: Boolean indicating if this is a resubmission
        process_folder: Optional folder path for processing
    """
    from .models import ProcessLogHdr, Pharmacy
    from .util import handle_zip_file
    import io

    logger.info(f"Starting Celery task for process_log_id={process_log_id}, is_resubmission={is_resubmission}")

    def mark_as_failed(error_message):
        """Helper to mark process as failed"""
        try:
            from .models import ProcessingStatus, ProcessingStatusCodes
            from core.utils import log_error
            process_log = ProcessLogHdr.objects.get(id=process_log_id)
            failed_status = ProcessingStatus.objects.get(code=ProcessingStatusCodes.Failed.value)
            process_log.status = failed_status
            process_log.save(update_fields=["status"])
            log_error(
                process_log=process_log,
                error_message=error_message,
                error_type="Task Failure",
                error_severity_code="ER",
                error_location="process_zip_file_task"
            )
            logger.error(f"Process marked as failed: {error_message}")
        except Exception as status_error:
            logger.error(f"Failed to update process log status: {str(status_error)}", exc_info=True)

    try:
        # Fetch database objects
        process_log = ProcessLogHdr.objects.get(id=process_log_id)
        obj = ProcessLogHdr.objects.get(id=obj_id)
        pharmacy = Pharmacy.objects.get(id=pharmacy_id) if pharmacy_id else None

        logger.info(f"Fetched pharmacy object: {pharmacy} (id={pharmacy.id if pharmacy else None})")

        # Read file from disk
        with open(file_path, 'rb') as f:
            file_data = io.BytesIO(f.read())

        # Process the file
        handle_zip_file(file_data, process_log, obj, pharmacy, is_resubmission, process_folder)

        logger.info(f"Successfully completed processing for process_log_id={process_log_id}")
        return {"status": "success", "process_log_id": process_log_id}

    except SoftTimeLimitExceeded:
        error_msg = f"Task exceeded time limit for process_log_id={process_log_id}"
        logger.error(error_msg, exc_info=True)
        mark_as_failed("Processing timed out - task exceeded maximum execution time")
        raise

    except KeyboardInterrupt:
        error_msg = f"Task interrupted for process_log_id={process_log_id}"
        logger.error(error_msg, exc_info=True)
        mark_as_failed("Processing was interrupted by system signal")
        raise

    except MemoryError:
        error_msg = f"Memory error processing file for process_log_id={process_log_id}"
        logger.error(error_msg, exc_info=True)
        mark_as_failed("Processing failed due to insufficient memory")
        raise

    except Exception as e:
        error_msg = f"Error processing file for process_log_id={process_log_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        mark_as_failed(f"Processing failed: {str(e)}")
        raise
