#!/usr/bin/env python3
"""Check consistency of the saved planning, tracking and reference evidence.

This is an artifact/hash consistency check. It does not rerun Gazebo, the
planner, geometric validation or the independent reference solver.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    artifacts={}
    def read(relative):
        path=ROOT/relative
        data=json.loads(path.read_text(encoding='utf-8'))
        artifacts[relative]=sha(path)
        return data
    def require(condition,message):
        if not condition:
            raise ValueError(message)
    benchmark=read('generated/funnel_benchmark/benchmark_results.json')
    reference=read('generated/funnel_reference/reference_comparison.json')
    comparison=read('generated/funnel_comparison/comparison_results.json')
    require(benchmark['complete'] and benchmark['all_cases_passed'],'Planning benchmark is incomplete or failed')
    require(reference['all_match_reference'],'A candidate does not match the reference')
    require(comparison['all_cases_passed'],'Tracking comparison has a failed case')
    require(benchmark['signature']==reference['benchmark_signature'],'Reference belongs to a different benchmark')
    mesh_relative='generated/funnel_input_y2p00.geom'
    artifacts[mesh_relative]=sha(ROOT/mesh_relative)
    require(reference['mesh_sha256']==artifacts[mesh_relative],'Navigation mesh changed since reference comparison')
    expected={'original','short_open','cross_city','narrow_corridor'}
    for name,data in (('benchmark',benchmark),('reference',reference),('comparison',comparison)):
        ids=[row.get('case',row.get('id')) for row in data['cases']]
        require(len(ids)==4 and set(ids)==expected,f'{name}: wrong or duplicate case set')
    rows=[]
    for case in ('original','short_open','cross_city','narrow_corridor'):
        b=next(row for row in benchmark['cases'] if row['id']==case)
        r=next(row for row in reference['cases'] if row['case']==case)
        c=next(row for row in comparison['cases'] if row['case']==case)
        require(b['status']=='PASS' and r['status']=='MATCHES_REFERENCE',f'{case}: planning/reference failed')
        candidate_relative='generated/funnel_benchmark/'+b['route_file']
        candidate=read(candidate_relative)
        require(sha(ROOT/candidate_relative)==r['funnel_route_sha256'],f'{case}: Funnel candidate changed')
        require(candidate['signature']==benchmark['signature'],f'{case}: stale candidate')
        require(abs(candidate['length']-r['funnel_length'])<1e-8,f'{case}: reference length mismatch')
        v=read(c['validation_file'])
        require(sha(ROOT/c['validation_file'])==c['validation_sha256'],f'{case}: validation changed; rerun summarize_funnel_experiments.py')
        require(v['checks_passed'] and v['last_phase']=='complete',f'{case}: tracking not complete/passed')
        route=read(c['route_file'])
        folder=(ROOT/c['route_file']).parent
        for relative,expected_hash in ((c['route_file'],v['route_sha256']),
                                      ((folder/'physics_telemetry.csv').relative_to(ROOT).as_posix(),v['telemetry_sha256'])):
            artifacts[relative]=sha(ROOT/relative)
            require(artifacts[relative]==expected_hash,f'{case}: route/telemetry changed; export and summarize again')
        metadata=read((folder/'telemetry_metadata.json').relative_to(ROOT).as_posix())
        require(metadata['route_sha256']==v['route_sha256'],f'{case}: controller metadata mismatch')
        source_relative=route.get('source_route_file','generated/funnel_route_candidate_y2p00.json')
        artifacts[source_relative]=sha(ROOT/source_relative)
        require(artifacts[source_relative]==route['source_route_sha256'],f'{case}: physics source route changed')
        require(abs(route['original_model_length']-r['funnel_length'])<1e-8,f'{case}: physics used a different route length')
        require(not v['obstacle_intersecting_sample_segments'] and c['speed_check_passed'],f'{case}: tracking clearance/speed failed')
        for metric in ('max_tracking_error','moving_rmse','final_goal_error','max_altitude_deviation','max_measured_speed'):
            require(v[metric]==c[metric],f'{case}: comparison metric {metric} is stale')
        rows.append({'case':case,'model_length':r['funnel_length'],'reference_length':r['reference_length'],
                     'max_tracking_error':v['max_tracking_error'],'moving_rmse':v['moving_rmse'],
                     'speed_limit':route['speed'],'max_measured_speed':v['max_measured_speed']})
        print(f'{case}: planning + tracking + reference evidence consistent',flush=True)
    out=ROOT/'generated/final_check'
    out.mkdir(exist_ok=True)
    report={'status':'READY','check_scope':'saved artifact/hash consistency only; no simulations or geometry checks rerun',
            'cases':rows,'artifact_sha256':artifacts,'general_algorithm_correctness_certified':False,
            'rotor_or_autopilot_simulation':False}
    path=out/'result_manifest.json'
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f'Save at: {path}',flush=True)
    lines=['# Kết quả đã kiểm tra của demo một UAV','',
           '**Trạng thái bộ file: READY.** Các báo cáo tìm đường, bám tuyến và đối chiếu tham chiếu của 4 ca nhất quán với dữ liệu nguồn hiện có.',
           '', 'Lần kiểm tra này chỉ kiểm tra tính nhất quán file và SHA256; không chạy lại Gazebo hoặc chứng minh hình học.',
           '', '| Ca thử | Độ dài mô hình gốc | Độ dài tham chiếu | Sai lệch bám tuyến lớn nhất | RMSE khi di chuyển |',
           '|---|---:|---:|---:|---:|']
    for row in rows:
        lines.append(f"| {row['case']} | {row['model_length']:.6f} | {row['reference_length']:.6f} | {row['max_tracking_error']:.9f} | {row['moving_rmse']:.9f} |")
    lines.extend(['','## Kết luận có thể sử dụng','',
                  'Trên bốn ca thử đã chọn của miền dẫn đường phẳng Y = 2, các tuyến Funnel thực nghiệm nằm trong miền và có độ dài khớp phương pháp tham chiếu độc lập trong dung sai số. Mô hình khối điểm điều khiển bằng lực đã hoàn tất các tuyến với sai lệch bám tuyến nhỏ. Không phát hiện giao với cột cản đã mở rộng ở các đoạn thẳng nối mẫu vị trí đo được.',
                  '', '## Giới hạn cần nêu trong báo cáo','',
                  '- Bằng chứng áp dụng cho bốn ca trên miền bay hiện tại; không chứng nhận thuật toán đúng/tối ưu trên mọi mesh hoặc bài toán tìm đường 3D.',
                  '- Mô hình động lực học là khối điểm 1 kg có bù trọng lực và điều khiển feedforward + PD. Chưa mô phỏng lực đẩy riêng từng rotor, attitude controller hay autopilot.',
                  '- Các đoạn nối mẫu CSV không phải chứng minh tránh va chạm liên tục theo thời gian.',
                  '- Hai ca dài có giới hạn tốc độ 5, hai ca ngắn có giới hạn 2; không dùng bảng sai lệch để xếp hạng công bằng giữa các ca.',
                  '- Đơn vị bản đồ và mô phỏng được chuẩn hóa từ asset, không phải tọa độ địa lý đo đạc.',
                  '', '## File cần dùng khi viết báo cáo','',
                  '- `generated/funnel_benchmark/benchmark_routes.png`: bốn ca tìm đường.',
                  '- `generated/funnel_comparison/comparison_report.md`: bảng kết quả bám tuyến.',
                  '- `generated/funnel_comparison/comparison_chart.png`: biểu đồ sai lệch và tốc độ.',
                  '- `generated/funnel_reference/reference_comparison.md`: bảng đối chiếu độ dài.',
                  '- `generated/funnel_reference/reference_routes.png`: tuyến Funnel và tuyến tham chiếu.',
                  '- `generated/final_check/result_manifest.json`: SHA256 và dữ liệu kết luận.',
                  '', 'Quy trình chạy lại và quy ước Ubuntu 1/Ubuntu 2 nằm trong `RUNBOOK_CURRENT.md` ở thư mục gốc dự án.'])
    path=out/'FINAL_RESULTS.md'
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(f'Save at: {path}',flush=True)
    print('Project results: READY',flush=True)


if __name__=='__main__':
    try:
        main()
    except (ValueError,KeyError,FileNotFoundError) as exc:
        raise SystemExit(f'Project results: NOT READY. {exc}')
