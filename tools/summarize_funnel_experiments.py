#!/usr/bin/env python3
"""Revalidate and compare four recorded point-mass tracking experiments."""
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
CASES=('original','short_open','cross_city','narrow_corridor')
LABELS={'original':'Tuyến ban đầu','short_open':'Vùng thoáng','cross_city':'Vòng vật cản trung tâm',
        'narrow_corridor':'Hành lang hẹp'}


def main():
    results=[]
    for case in CASES:
        folder=ROOT/'generated/funnel_physics'
        if case!='original':
            folder=folder/case
        checked=subprocess.run([sys.executable,str(ROOT/'tools/analyze_funnel_physics.py'),'--case',case],
                               cwd=ROOT,capture_output=True,text=True)
        if checked.returncode:
            print(checked.stdout+checked.stderr,file=sys.stderr)
            raise SystemExit(f'{case}: validation failed or mission incomplete; no comparison exported.')
        validation_path=folder/'physics_validation.json'
        report=json.loads(validation_path.read_text())
        route_path=folder/'route.json'
        route=json.loads(route_path.read_text())
        raw=(folder/'physics_telemetry.csv').read_bytes()
        if hashlib.sha256(raw).hexdigest()!=report['telemetry_sha256']:
            raise SystemExit('Telemetry changed. Close Gazebo and rerun this summary command.')
        rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8'))))
        first_complete=next(float(row['sim_time']) for row in rows if row['phase']=='complete')
        result={'case':case,'label':LABELS[case],'checks_passed':report['checks_passed'],
                'original_model_length':route['original_model_length'],'simulation_length':route['length'],
                'reference_speed_limit':route['speed'],'max_measured_speed':report['max_measured_speed'],
                'max_tracking_error':report['max_tracking_error'],'moving_rmse':report['moving_rmse'],
                'final_goal_error':report['final_goal_error'],
                'max_altitude_deviation':report['max_altitude_deviation'],
                'first_complete_elapsed_sim_seconds':first_complete-float(rows[0]['sim_time']),
                'samples':report['samples'],'intersecting_sample_segments':len(report['obstacle_intersecting_sample_segments']),
                'speed_check_passed':report['max_measured_speed']<=route['speed']+.01,
                'route_file':route_path.relative_to(ROOT).as_posix(),
                'validation_file':validation_path.relative_to(ROOT).as_posix(),
                'validation_sha256':hashlib.sha256(validation_path.read_bytes()).hexdigest(),
                'route_sha256':report['route_sha256'],'telemetry_sha256':report['telemetry_sha256']}
        results.append(result)
        print(f"{case}: PASS | max error={result['max_tracking_error']:.6f} | moving RMSE={result['moving_rmse']:.6f}",flush=True)
    out=ROOT/'generated/funnel_comparison'
    out.mkdir(exist_ok=True)
    all_passed=all(row['checks_passed'] and row['speed_check_passed'] for row in results)
    comparison={'all_cases_passed':all_passed,'cases':results,'units':'normalized model/simulation units, not surveyed metres',
                'comparison_scope':'observations under different route geometries, speed limits and startup delays; not a controlled performance ranking',
                'model':'1 kg point mass, gravity compensation, feedforward and PD feedback; decorative rotors',
                'collision_check_scope':'measured centres and straight segments between CSV samples vs inflated obstacle columns; not continuous-time contact proof',
                'global_route_optimality_certified':False}
    path=out/'comparison_results.json'
    path.write_text(json.dumps(comparison,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Save at: {path}',flush=True)
    lines=['# Tổng hợp 4 ca mô phỏng bám tuyến Funnel','',
           f'Kết quả: **{"4/4 ca đạt" if all_passed else "Có kiểm tra chưa đạt"}**. Mỗi ca đã được kiểm tra lại từ CSV đo trong Gazebo.',
           '', '| Ca thử | Độ dài (mô hình gốc) | Giới hạn tốc độ | Sai lệch lớn nhất | RMSE khi di chuyển | Sai lệch cuối tới GOAL |',
           '|---|---:|---:|---:|---:|---:|']
    for row in results:
        lines.append(f"| {row['label']} (`{row['case']}`) | {row['original_model_length']:.6f} | {row['reference_speed_limit']:.1f} | {row['max_tracking_error']:.9f} | {row['moving_rmse']:.9f} | {row['final_goal_error']:.3e} |")
    lines.extend(['','Độ dài dùng đơn vị mô hình gốc. Sai lệch dùng đơn vị mô phỏng; tốc độ dùng đơn vị mô phỏng/giây.',
                  '', '| Ca thử | Độ dài mô phỏng | Tốc độ đo lớn nhất | Thời điểm hoàn tất (giây mô phỏng) | Số mẫu | Số đoạn nối mẫu giao cột cản |',
                  '|---|---:|---:|---:|---:|---:|'])
    for row in results:
        lines.append(f"| {row['case']} | {row['simulation_length']:.6f} | {row['max_measured_speed']:.6f} | {row['first_complete_elapsed_sim_seconds']:.3f} | {row['samples']} | {row['intersecting_sample_segments']} |")
    lines.extend(['','## Nhận xét','',
                  '- Cả bốn lượt đã tới trạng thái `complete`; sai lệch bám tuyến nhỏ trong mô hình đang dùng.',
                  '- Thời điểm hoàn tất lấy từ mẫu CSV đầu tiên có trạng thái `complete`, không cộng thời gian tiếp tục giữ vị trí ở đích.',
                  '- RMSE chỉ tính các mẫu có trạng thái `moving`, tránh làm kết quả thấp đi do thời gian chờ hoặc giữ vị trí kéo dài.',
                  '- Hai ca dài có giới hạn tốc độ 5; hai ca ngắn có giới hạn 2 và thời gian chờ ban đầu dài hơn. Các số liệu không phải phép so sánh công bằng về hiệu năng thuật toán hoặc chất lượng bộ điều khiển.',
                  '', '## Phạm vi kết luận','',
                  '- Drone là khối điểm 1 kg có bù trọng lực và điều khiển lực feedforward + PD; chưa có lực đẩy từng rotor, attitude controller hay autopilot.',
                  '- Không phát hiện giao với mô hình cột cản đã mở rộng ở các đoạn thẳng nối mẫu đo. Đây không phải chứng minh tránh va chạm liên tục theo thời gian hay bằng cảm biến tiếp xúc.',
                  '- Bản đồ được chuẩn hóa tỉ lệ để mô phỏng; không quy đổi các sai lệch trên thành độ chính xác ngoài thực địa.',
                  '- Bốn ca đạt là bằng chứng thực nghiệm trong bộ thử này, chưa chứng nhận Funnel Tree đúng/tối ưu trên mọi bản đồ hoặc tuyến ngắn nhất toàn cục.',
                  '', '## Dữ liệu nguồn','',
                  'Các đường dẫn và SHA256 của route, telemetry và báo cáo kiểm tra được ghi trong `comparison_results.json`.'])
    path=out/'comparison_report.md'
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(f'Save at: {path}',flush=True)

    names=[row['case'].replace('_','\n') for row in results]
    x=np.arange(len(results))
    fig,axes=plt.subplots(1,2,figsize=(12,5.5))
    axes[0].bar(x-.19,[row['max_tracking_error'] for row in results],width=.36,color='#2564b3',label='Maximum position error')
    axes[0].bar(x+.19,[row['moving_rmse'] for row in results],width=.36,color='#e58b2d',label='RMSE while moving')
    axes[0].set(ylabel='Tracking error (simulation units)',title='Measured tracking errors')
    axes[0].legend(fontsize=9)
    axes[0].ticklabel_format(axis='y',style='sci',scilimits=(-3,-3))
    for i,row in enumerate(results):
        axes[0].annotate(f"{row['max_tracking_error']:.5f}",(i-.19,row['max_tracking_error']),
                         xytext=(0,4),textcoords='offset points',ha='center',fontsize=8)
    axes[0].margins(y=.2)
    axes[1].bar(x,[row['max_measured_speed'] for row in results],color='#21885e',width=.55,label='Maximum measured speed')
    axes[1].scatter(x,[row['reference_speed_limit'] for row in results],marker='_',s=350,color='#a6203d',label='Reference speed limit',zorder=4)
    axes[1].set(ylabel='Speed (simulation units/s)',title='Speed settings differ between cases',ylim=(0,6))
    axes[1].legend(fontsize=9)
    for ax in axes:
        ax.set_xticks(x,names)
        ax.spines[['top','right']].set_visible(False)
        ax.grid(axis='y',alpha=.2)
        ax.set_axisbelow(True)
    fig.suptitle('Four force-driven Funnel tracking experiments')
    fig.text(.5,.025,'Point-mass simulation. Different routes and speed settings; no global optimality claim.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.06,1,.95))
    path=out/'comparison_chart.png'
    fig.savefig(path,dpi=180)
    plt.close(fig)
    print(f'Save at: {path}',flush=True)
    print(f'All cases passed: {all_passed}',flush=True)
    if not all_passed:
        raise SystemExit(1)


if __name__=='__main__':
    main()
