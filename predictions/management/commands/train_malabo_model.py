"""
Train ML model: rain + sensors → malabo na bukal.

Usage:
  python manage.py train_malabo_model
  python manage.py train_malabo_model --synthetic 1000
  python manage.py train_malabo_model --no-real
"""
from django.core.management.base import BaseCommand

from predictions.ml_engine import dataset_csv_path, model_path, train_model


class Command(BaseCommand):
    help = 'Train RandomForest model to predict malabo na tubig-bukal'

    def add_arguments(self, parser):
        parser.add_argument(
            '--synthetic',
            type=int,
            default=2000,
            help='Number of synthetic training samples (default 2000)',
        )
        parser.add_argument(
            '--no-real',
            action='store_true',
            help='Do not include real WaterQuality rows',
        )

    def handle(self, *args, **options):
        self.stdout.write('Training malabo ML model...')
        meta = train_model(
            n_synthetic=options['synthetic'],
            use_real=not options['no_real'],
        )
        self.stdout.write(self.style.SUCCESS('Training complete.'))
        self.stdout.write(f"  Algorithm : {meta['algorithm']}")
        self.stdout.write(f"  Samples   : {meta['n_samples_total']} "
                          f"(real={meta['n_samples_real']}, synthetic={meta['n_samples_synthetic']})")
        self.stdout.write(f"  Accuracy  : {meta['accuracy']:.2%}")
        self.stdout.write(f"  F1 score  : {meta['f1']:.4f}")
        self.stdout.write(f"  Model     : {model_path()}")
        self.stdout.write(f"  Dataset   : {dataset_csv_path()}")
        self.stdout.write('')
        self.stdout.write('Top features:')
        imps = sorted(meta['feature_importances'].items(), key=lambda x: -x[1])
        for name, imp in imps[:5]:
            self.stdout.write(f"  - {name}: {imp:.3f}")
