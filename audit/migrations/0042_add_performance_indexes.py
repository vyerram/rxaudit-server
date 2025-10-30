# Generated migration for performance indexes

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0041_filedbmapping_volume_group_and_more'),
    ]

    operations = [
        # Add index on PharmacyAuditData.process_log for faster filtering
        migrations.AddIndex(
            model_name='pharmacyauditdata',
            index=models.Index(fields=['process_log'], name='idx_pad_process_log'),
        ),
        # Add index on DistributorAuditData.process_log for faster filtering
        migrations.AddIndex(
            model_name='distributorauditdata',
            index=models.Index(fields=['process_log'], name='idx_dad_process_log'),
        ),
        # Add index on ProcessLogDetail.process_log for faster filtering
        migrations.AddIndex(
            model_name='processlogdetail',
            index=models.Index(fields=['process_log'], name='idx_pld_process_log'),
        ),
        # Add index on FileDBMapping.pharmacy_software for faster lookups
        migrations.AddIndex(
            model_name='filedbmapping',
            index=models.Index(fields=['pharmacy_software'], name='idx_fmp_pharm_soft'),
        ),
        # Add composite index on FileDBMapping for distributor lookups
        migrations.AddIndex(
            model_name='filedbmapping',
            index=models.Index(fields=['distributor', 'file_type'], name='idx_fmp_dist_type'),
        ),
        # Add index on ProcessLogHdr.status for filtering by status
        migrations.AddIndex(
            model_name='processloghdr',
            index=models.Index(fields=['status'], name='idx_plg_status'),
        ),
        # Add composite index on PharmacyAuditData for date range queries
        migrations.AddIndex(
            model_name='pharmacyauditdata',
            index=models.Index(fields=['process_log', 'date'], name='idx_pad_log_date'),
        ),
        # Add composite index on DistributorAuditData for date range queries
        migrations.AddIndex(
            model_name='distributorauditdata',
            index=models.Index(fields=['process_log', 'date'], name='idx_dad_log_date'),
        ),
    ]
