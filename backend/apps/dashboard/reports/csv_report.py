import csv

from django.http import HttpResponse


def csv_response(filename, header, rows):
    """Streams a simple CSV as an attachment. `rows` is a list of lists,
    already in the exact column order of `header`."""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(header)
    writer.writerows(rows)
    return response
