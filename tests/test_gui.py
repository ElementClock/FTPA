import os
import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from ftpa.gui.services import build_analysis_preview, get_data_fields, run_analysis


def test_get_data_fields_reads_header():
    temp_dir = tempfile.mkdtemp()
    try:
        path = os.path.join(temp_dir, 'data.txt')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('TIME\t无线电高度表决值\t指示空速表决值\n')
            f.write('00:00:00:000\t1\t2\n')

        fields = get_data_fields(path)
        assert fields == ['TIME', '无线电高度表决值', '指示空速表决值']
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_build_analysis_preview_returns_plot_data_for_missing_file():
    result = build_analysis_preview(data_path='missing_file.txt', excel_path='missing_labels.xlsx')
    assert '数据文件' in result['summary_lines'][0]
    assert len(result['plot_series']) >= 1
    assert len(result['plot_labels']) == len(result['plot_series'])


def test_run_analysis_with_valid_temp_file():
    temp_dir = tempfile.mkdtemp()
    try:
        data_path = os.path.join(temp_dir, 'test_data.txt')
        with open(data_path, 'w', encoding='utf-8') as f:
            f.write('TIME\tCol1\tCol2\n')
            for i in range(120):
                f.write(f'00:00:{i:02d}:000\t{i}.0\t{i*2}.0\n')

        result = run_analysis(data_path=data_path, excel_path='missing_labels.xlsx', selected_signals=['Col1', 'Col2'])
        assert result['row_count'] == 20
        assert '标签文件' in result['summary_lines'][1]
        assert len(result['plot_series']) == 2
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
