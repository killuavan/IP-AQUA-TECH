"""Report generation and download views."""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import ReportGenerateForm
from .models import Report, ReportFormat, ReportType
from .utils import gather_report_data, generate_pdf, generate_excel


@login_required
def report_list(request):
    qs = Report.objects.select_related('generated_by').all()
    paginator = Paginator(qs, 12)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'reports/report_list.html', {'page_obj': page})


@login_required
@require_http_methods(['GET', 'POST'])
def report_generate(request):
    today = timezone.now().date()
    initial = {
        'title': f'Daily Report – {today}',
        'report_type': ReportType.DAILY,
        'report_format': ReportFormat.BOTH,
        'start_date': today,
        'end_date': today,
    }
    form = ReportGenerateForm(request.POST or None, initial=initial)

    if request.method == 'POST' and form.is_valid():
        title = form.cleaned_data['title']
        report_type = form.cleaned_data['report_type']
        report_format = form.cleaned_data['report_format']
        start_date = form.cleaned_data['start_date']
        end_date = form.cleaned_data['end_date']

        data = gather_report_data(start_date, end_date)
        report = Report(
            title=title,
            report_type=report_type,
            report_format=report_format,
            start_date=start_date,
            end_date=end_date,
            generated_by=request.user,
            summary=(
                f'Production: {data["production"]["total_liters"]} L | '
                f'WQ readings: {data["water_quality"]["count"]} | '
                f'Alerts: {data["alerts"]["total"]}'
            ),
        )
        report.save()

        if report_format in (ReportFormat.PDF, ReportFormat.BOTH):
            pdf_bytes = generate_pdf(data, title)
            report.file_pdf.save(
                f'report_{report.pk}_{start_date}.pdf',
                ContentFile(pdf_bytes),
                save=False,
            )
        if report_format in (ReportFormat.EXCEL, ReportFormat.BOTH):
            xlsx_bytes = generate_excel(data, title)
            report.file_excel.save(
                f'report_{report.pk}_{start_date}.xlsx',
                ContentFile(xlsx_bytes),
                save=False,
            )
        report.save()
        messages.success(request, 'Report generated successfully.')
        return redirect('reports:report_detail', pk=report.pk)

    # Quick presets
    presets = {
        'daily': (today, today),
        'weekly': (today - timedelta(days=today.weekday()), today),
        'monthly': (today.replace(day=1), today),
        'annual': (today.replace(month=1, day=1), today),
    }
    return render(request, 'reports/report_generate.html', {
        'form': form,
        'presets': presets,
    })


@login_required
def report_detail(request, pk):
    report = get_object_or_404(Report.objects.select_related('generated_by'), pk=pk)
    return render(request, 'reports/report_detail.html', {'report': report})


@login_required
def report_download_pdf(request, pk):
    report = get_object_or_404(Report, pk=pk)
    if report.file_pdf:
        response = HttpResponse(report.file_pdf.read(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{report.title}.pdf"'
        return response
    # Generate on the fly
    data = gather_report_data(report.start_date, report.end_date)
    pdf_bytes = generate_pdf(data, report.title)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{report.title}.pdf"'
    return response


@login_required
def report_download_excel(request, pk):
    report = get_object_or_404(Report, pk=pk)
    if report.file_excel:
        response = HttpResponse(
            report.file_excel.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="{report.title}.xlsx"'
        return response
    data = gather_report_data(report.start_date, report.end_date)
    xlsx_bytes = generate_excel(data, report.title)
    response = HttpResponse(
        xlsx_bytes,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{report.title}.xlsx"'
    return response


@login_required
@require_http_methods(['POST'])
def report_delete(request, pk):
    report = get_object_or_404(Report, pk=pk)
    if report.file_pdf:
        report.file_pdf.delete(save=False)
    if report.file_excel:
        report.file_excel.delete(save=False)
    report.delete()
    messages.success(request, 'Report deleted.')
    return redirect('reports:report_list')
