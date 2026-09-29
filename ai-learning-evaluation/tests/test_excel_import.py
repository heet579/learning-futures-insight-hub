"""Tiny OOXML fixtures exercise the real Excel reader without an authoring dependency."""
from html import escape
from zipfile import ZipFile
import io

import pandas as pd
import pytest

from src.ingestion.qualtrics_loader import load_survey
from test_qualtrics_real_export import _fake_export_csv


def write_xlsx_fixture(path, frame):
    rows = [list(frame.columns), *frame.fillna("").astype(str).values.tolist()]
    sheet = '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
    for index, row in enumerate(rows, 1):
        sheet += f'<row r="{index}">'
        for col, value in enumerate(row, 1):
            name, number = "", col
            while number:
                number, remainder = divmod(number - 1, 26)
                name = chr(65 + remainder) + name
            sheet += f'<c r="{name}{index}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'
        sheet += '</row>'
    sheet += '</sheetData></worksheet>'
    with ZipFile(path, 'w') as archive:
        archive.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Survey" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr('xl/worksheets/sheet1.xml', sheet)


def test_raw_qualtrics_excel_matches_csv(tmp_path):
    csv = tmp_path / '8325+-+Fake+Course.csv'
    excel = csv.with_suffix('.xlsx')
    csv.write_text(_fake_export_csv(), encoding='utf-8')
    write_xlsx_fixture(excel, pd.read_csv(csv))
    pd.testing.assert_frame_equal(load_survey(csv), load_survey(excel))


def test_canonical_excel_preserves_rows_and_columns(tmp_path, golden_df):
    excel = tmp_path / 'canonical.xlsx'
    write_xlsx_fixture(excel, golden_df)
    loaded = load_survey(excel)
    assert len(loaded) == 3
    assert loaded.columns.tolist() == golden_df.columns.tolist()
    assert pd.to_numeric(loaded['OverallSatisfaction']).tolist() == [5, 3, 4]


def test_corrupt_excel_has_useful_error(tmp_path):
    path = tmp_path / 'bad.xlsx'
    path.write_bytes(b'not a workbook')
    with pytest.raises(ValueError, match='first sheet'):
        load_survey(path)


def test_numeric_qualtrics_ratings_and_new_enjoyed_question(tmp_path):
    raw = pd.read_csv(io.StringIO(_fake_export_csv()))
    raw.loc[0, 'Q7'] = 'The aspects about studying with PACE that I enjoyed the most were: - Selected Choice'
    raw.loc[2, 'Q2_1'] = '5'
    path = tmp_path / '8325+-+Course.csv'
    raw.to_csv(path, index=False)
    loaded = load_survey(path)
    assert loaded['OverallSatisfaction'].tolist() == [5, 2]
    assert loaded['MostValuableAspect'].iloc[0] == 'Placeholder positive comment'


def test_braces_in_real_comments_do_not_delete_responses(tmp_path, golden_df):
    golden_df.loc[0, 'AdditionalComments'] = 'Discuss {examples} next time'
    path = tmp_path / 'canonical.csv'
    golden_df.to_csv(path, index=False)
    assert len(load_survey(path)) == 3
