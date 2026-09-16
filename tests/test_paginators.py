from datetime import datetime, timedelta, timezone

import pytest
from requests import Request, Response
from merit.paginators import MeritDatePaginator


def pages(start, end, interval=30, date_type=0, params=None):
    paginator = MeritDatePaginator(start, end, interval, date_type)
    request = Request(params=params)
    paginator.init_request(request)
    result = []
    for _ in range(400):
        result.append(dict(request.params))
        paginator.update_state(Response(), [])
        if not paginator.has_next_page:
            return result
        paginator.update_request(request)
    pytest.fail('Paginator did not terminate')


@pytest.mark.parametrize('start,end,interval', [
    ('20260601', '20260630', 30),
    ('20260601', '20260701', 30),
    ('20260630', '20260630', 30),
    ('20240201', '20240301', 7),
    ('20251201', '20260228', 30),
    ('20260601', '20260603', 1),
    ('20260101', '20260630', 90),
])
def test_document_dates_cover_every_day_exactly_once(start, end, interval):
    first = datetime.strptime(start, '%Y%m%d')
    last = datetime.strptime(end, '%Y%m%d')
    covered = []
    for page in pages(first, last, interval):
        a = datetime.strptime(page['PeriodStart'], '%Y%m%d')
        b = datetime.strptime(page['PeriodEnd'], '%Y%m%d')
        assert page['DateType'] == 0
        assert 1 <= (b - a).days + 1 <= interval
        covered.extend(a + timedelta(days=i) for i in range((b-a).days+1))
    assert covered == [first + timedelta(days=i) for i in range((last-first).days+1)]


def test_june_boundary_batches_are_not_requested_twice():
    result = pages(datetime(2026, 6, 1), datetime(2026, 7, 1))
    assert [(p['PeriodStart'], p['PeriodEnd']) for p in result] == [
        ('20260601', '20260630'), ('20260701', '20260701')]


def test_changed_date_retains_exclusive_boundary():
    result = pages(datetime(2026, 6, 1), datetime(2026, 7, 1), date_type=1)
    assert [(p['PeriodStart'], p['PeriodEnd']) for p in result] == [
        ('20260601', '20260630'), ('20260630', '20260701')]


def test_one_day_changed_date_windows_advance():
    result = pages(datetime(2026, 6, 1), datetime(2026, 6, 3), interval=1, date_type=1)
    assert len(result) == 2
    assert result[-1]['PeriodEnd'] == '20260603'


def test_existing_cursor_and_parameters_are_preserved():
    result = pages(datetime(2026, 6, 1, tzinfo=timezone.utc),
                   datetime(2026, 6, 30, tzinfo=timezone.utc),
                   params={'PeriodStart': '20260630', 'WithLines': 1})
    assert result == [{'PeriodStart': '20260630', 'PeriodEnd': '20260630',
                       'DateType': 0, 'WithLines': 1}]


@pytest.mark.parametrize('interval', [0, -1, 91])
def test_invalid_intervals(interval):
    with pytest.raises(ValueError):
        MeritDatePaginator(datetime(2026, 6, 1), datetime(2026, 6, 30), interval)
