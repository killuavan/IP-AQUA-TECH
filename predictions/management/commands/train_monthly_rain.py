"""Train ML models: monthly rain + chance na lalabo pag umulan."""
from django.core.management.base import BaseCommand

from predictions.monthly_rain import (
    cloud_dataset_path,
    cloud_model_path,
    monthly_dataset_path,
    monthly_model_path,
    train_monthly_rain_model,
)


class Command(BaseCommand):
    help = 'Train RandomForest: monthly rain + spring cloud (lalabo) chance'

    def handle(self, *args, **options):
        self.stdout.write('Training monthly rain + spring cloud ML...')
        meta = train_monthly_rain_model()
        cloud = meta.get('spring_cloud') or {}
        self.stdout.write(self.style.SUCCESS('Done.'))
        self.stdout.write('--- Monthly rain ---')
        self.stdout.write(f"  Samples     : {meta['n_samples']}")
        self.stdout.write(f"  Level acc   : {meta['accuracy_level']:.2%}")
        self.stdout.write(f"  MAE mm      : {meta['mae_total_mm']}")
        self.stdout.write(f"  Model       : {monthly_model_path()}")
        self.stdout.write(f"  Dataset CSV : {monthly_dataset_path()}")
        self.stdout.write('--- Chance lalabo pag umulan (ML) ---')
        self.stdout.write(f"  Samples     : {cloud.get('n_samples')}")
        self.stdout.write(f"  Accuracy    : {cloud.get('accuracy')}")
        self.stdout.write(f"  F1          : {cloud.get('f1')}")
        self.stdout.write(f"  ROC-AUC     : {cloud.get('roc_auc')}")
        self.stdout.write(f"  Model       : {cloud_model_path()}")
        self.stdout.write(f"  Dataset CSV : {cloud_dataset_path()}")
