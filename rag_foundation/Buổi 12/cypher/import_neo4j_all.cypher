// BƯỚC 8.1 — Uniqueness constraints (chạy trước khi import)
CREATE CONSTRAINT doc_so_ky_hieu IF NOT EXISTS
FOR (d:Document) REQUIRE d.so_ky_hieu IS UNIQUE;
CREATE CONSTRAINT coquan_name IF NOT EXISTS
FOR (n:CoQuan) REQUIRE n.canonical_name IS UNIQUE;
CREATE CONSTRAINT nguoiky_name IF NOT EXISTS
FOR (n:NguoiKy) REQUIRE n.canonical_name IS UNIQUE;
CREATE CONSTRAINT dtad_name IF NOT EXISTS
FOR (n:DoiTuongApDung) REQUIRE n.canonical_name IS UNIQUE;
CREATE CONSTRAINT linhvuc_name IF NOT EXISTS
FOR (n:LinhVuc) REQUIRE n.canonical_name IS UNIQUE;

// BƯỚC 8.2 — Document nodes (MERGE => idempotent)
UNWIND [
  {id: '166170', so_ky_hieu: '32/2024/QH15', title: 'Luật Các tổ chức tín dụng số 32/2024/QH15', loai_van_ban: 'Luật', ngay_ban_hanh: '18/01/2024', ngay_co_hieu_luc: '01/07/2024', tinh_trang_hieu_luc: 'Hết hiệu lực một phần', co_quan_ban_hanh: 'Quốc hội'},
  {id: '112025', so_ky_hieu: '73/2016/NĐ-CP', title: 'Nghị định số 73/2016/NĐ-CP Quy định chi tiết thi hành Luật kinh doanh bảo hiểm và Luật sửa đổi, bổ sung một số điều của Luật kinh doanh bảo hiểm', loai_van_ban: 'Nghị định', ngay_ban_hanh: '01/07/2016', ngay_co_hieu_luc: '01/07/2016', tinh_trang_hieu_luc: 'Hết hiệu lực một phần', co_quan_ban_hanh: 'Chính phủ'},
  {id: '38128', so_ky_hieu: '37/2014/TT-NHNN', title: 'Thông tư số 37/2014/TT-NHNN Quy định việc thiết kế mẫu tiền, chế bản và quản lý in, đúc tiền Việt Nam', loai_van_ban: 'Thông tư', ngay_ban_hanh: '26/11/2014', ngay_co_hieu_luc: '12/01/2015', tinh_trang_hieu_luc: 'Hết hiệu lực một phần', co_quan_ban_hanh: 'Ngân hàng Nhà nước Việt Nam'},
  {id: '26750', so_ky_hieu: '67/2011/QH12', title: 'Luật Kiểm toán độc lập số 67/2011/QH12', loai_van_ban: 'Luật', ngay_ban_hanh: '29/03/2011', ngay_co_hieu_luc: '01/01/2012', tinh_trang_hieu_luc: 'Hết hiệu lực một phần', co_quan_ban_hanh: 'Quốc hội'},
  {id: '163441', so_ky_hieu: '46/2023/NĐ-CP', title: 'Nghị định số 46/2023/NĐ-CP Quy định chi tiết thi hành một số điều của Luật Kinh doanh bảo hiểm', loai_van_ban: 'Nghị định', ngay_ban_hanh: '01/07/2023', ngay_co_hieu_luc: '01/07/2023', tinh_trang_hieu_luc: 'Hết hiệu lực một phần', co_quan_ban_hanh: 'Chính phủ'},
  {id: '146468', so_ky_hieu: '156/2020/NĐ-CP', title: 'Nghị định số 156/2020/NĐ-CP Quy định xử phạt vi phạm hành chính trong lĩnh vực chứng khoán và thị trường chứng khoán', loai_van_ban: 'Nghị định', ngay_ban_hanh: '31/12/2020', ngay_co_hieu_luc: '01/01/2021', tinh_trang_hieu_luc: 'Hết hiệu lực một phần', co_quan_ban_hanh: 'Chính phủ'},
  {id: '168220', so_ky_hieu: '27/2024/TT-NHNN', title: 'Thông tư số 27/2024/TT-NHNN Quy định về việc ngân hàng hợp tác xã, việc trích nộp, quản lý và sử dụng Quỹ bảo đảm an toàn hệ thống quỹ tín dụng nhân dân', loai_van_ban: 'Thông tư', ngay_ban_hanh: '28/06/2024', ngay_co_hieu_luc: '01/07/2024', tinh_trang_hieu_luc: 'Hết hiệu lực một phần', co_quan_ban_hanh: 'Ngân hàng Nhà nước Việt Nam'},
  {id: '133858', so_ky_hieu: '05/2019/NĐ-CP', title: 'Nghị định số 05/2019/NĐ-CP Về kiểm toán nội bộ', loai_van_ban: 'Nghị định', ngay_ban_hanh: '22/01/2019', ngay_co_hieu_luc: '01/04/2019', tinh_trang_hieu_luc: 'Còn hiệu lực', co_quan_ban_hanh: 'Chính phủ'},
  {id: '169221', so_ky_hieu: '43/2024/TT-NHNN', title: 'Thông tư số 43/2024/TT-NHNN sửa đổi, bổ sung một số điều của Thông tư số 01/2014/TT-NHNN ngày 10 tháng 12 năm 2014 của Thống đốc Ngân hàng Nhà nước Việt Nam hướng dẫn việc tổ chức thực hiện hoạt đọng quản lý dự trữ ngoại hối nhà nước.', loai_van_ban: 'Thông tư', ngay_ban_hanh: '09/08/2024', ngay_co_hieu_luc: '23/09/2024', tinh_trang_hieu_luc: 'Còn hiệu lực', co_quan_ban_hanh: 'Ngân hàng Nhà nước Việt Nam'},
  {id: '95652', so_ky_hieu: '135/2015/NĐ-CP', title: 'Nghị định số 135/2015/NĐ-CP Quy định về đầu tư gián tiếp ra nước ngoài', loai_van_ban: 'Nghị định', ngay_ban_hanh: '31/12/2015', ngay_co_hieu_luc: '15/02/2016', tinh_trang_hieu_luc: 'Hết hiệu lực một phần', co_quan_ban_hanh: 'Chính phủ'},
  {id: 'f69936f0-6937-11f1-a48d-29bc6b0fd706', so_ky_hieu: '17/VBHN-BTC', title: 'Văn bản hợp nhất Nghị định số 156/2020/NĐ-CP Quy định xử phạt vi phạm hành chính trong lĩnh vực chứng khoán và thị trường chứng khoán', loai_van_ban: 'Văn bản hợp nhất', ngay_ban_hanh: '13/05/2026', ngay_co_hieu_luc: null, tinh_trang_hieu_luc: 'Chưa xác định', co_quan_ban_hanh: 'Bộ Tài chính'},
  {id: '30402', so_ky_hieu: '202/2012/TT-BTC', title: 'Thông tư số 202/2012/TT-BTC Hướng dẫn về đăng ký, quản lý và công khai danh sách kiểm toán viên hành nghề kiểm toán', loai_van_ban: 'Thông tư', ngay_ban_hanh: '19/11/2012', ngay_co_hieu_luc: '01/03/2013', tinh_trang_hieu_luc: 'Hết hiệu lực một phần', co_quan_ban_hanh: 'Bộ Tài chính'},
  {id: '173460', so_ky_hieu: '57/2024/TT-NHNN', title: 'Thông tư số 57/2024/TT-NHNN Quy định hồ sơ, thủ tục cấp Giấy phép lần đầu của tổ chức tín dụng phi ngân hàng', loai_van_ban: 'Thông tư', ngay_ban_hanh: '24/12/2024', ngay_co_hieu_luc: '24/12/2024', tinh_trang_hieu_luc: 'Hết hiệu lực một phần', co_quan_ban_hanh: 'Ngân hàng Nhà nước Việt Nam'},
  {id: '27257', so_ky_hieu: '44/2011/TT-NHNN', title: 'Thông tư số 44/2011/TT-NHNN Quy định về hệ thống kiểm soát nội bộ và kiểm toán nội bộ của tổ chức tín dụng, chi nhánh ngân hàng nước ngoài', loai_van_ban: 'Thông tư', ngay_ban_hanh: '29/12/2011', ngay_co_hieu_luc: '12/02/2012', tinh_trang_hieu_luc: 'Hết hiệu lực một phần', co_quan_ban_hanh: 'Ngân hàng Nhà nước Việt Nam'},
  {id: '143217', so_ky_hieu: '66/2020/TT-BTC', title: 'Thông tư số 66/2020/TT-BTC Ban hành Quy chế mẫu về kiểm toán nội bộ áp dụng cho doanh nghiệp', loai_van_ban: 'Thông tư', ngay_ban_hanh: '10/07/2020', ngay_co_hieu_luc: '01/09/2020', tinh_trang_hieu_luc: 'Còn hiệu lực', co_quan_ban_hanh: 'Bộ Tài chính'},
  {id: '168859', so_ky_hieu: '29/2024/TT-NHNN', title: 'Thông tư số 29/2024/TT-NHNN Quy định về quỹ tín dụng nhân dân', loai_van_ban: 'Thông tư', ngay_ban_hanh: '28/06/2024', ngay_co_hieu_luc: '01/07/2024', tinh_trang_hieu_luc: 'Hết hiệu lực một phần', co_quan_ban_hanh: 'Ngân hàng Nhà nước Việt Nam'},
  {id: '150974', so_ky_hieu: '08/2021/TT-BTC', title: 'Thông tư số 08/2021/TT-BTC Ban hành chuẩn mực kiểm toán nội bộ Việt Nam và các nguyên tắc đạo đức nghề nghiệp kiểm toán nội bộ', loai_van_ban: 'Thông tư', ngay_ban_hanh: '25/01/2021', ngay_co_hieu_luc: '01/04/2021', tinh_trang_hieu_luc: 'Còn hiệu lực', co_quan_ban_hanh: 'Bộ Tài chính'},
  {id: '164719', so_ky_hieu: '22/2023/TT-NHNN', title: 'Thông tư số 22/2023/TT-NHNN Sửa đổi, bổ sung một số điều của Thông tư số 41/2016/TT-NHNN ngày 30 tháng 12 năm 2016 của Thống đốc Ngân hàng Nhà nước Việt Nam quy định tỷ lệ an toàn vốn đối với ngân hàng, chi nhánh ngân hàng nước ngoài', loai_van_ban: 'Thông tư', ngay_ban_hanh: '29/12/2023', ngay_co_hieu_luc: '01/07/2024', tinh_trang_hieu_luc: 'Còn hiệu lực', co_quan_ban_hanh: 'Ngân hàng Nhà nước Việt Nam'},
  {id: '173695', so_ky_hieu: '56/2024/TT-NHNN', title: 'Thông tư số 56/2024/TT-NHNN Quy định hồ sơ, thủ tục cấp Giấy phép lần đầu của ngân hàng thương mại, chi nhánh ngân hàng nước ngoài, văn phòng đại diện nước ngoài', loai_van_ban: 'Thông tư', ngay_ban_hanh: '24/12/2024', ngay_co_hieu_luc: '24/12/2024', tinh_trang_hieu_luc: 'Hết hiệu lực một phần', co_quan_ban_hanh: 'Ngân hàng Nhà nước Việt Nam'},
  {id: '186482', so_ky_hieu: '69/2025/TT-NHNN', title: 'Thông tư số 69/2025/TT-NHNN ửa đổi, bổ sung một số điều của một số Thông tư của Thống đốc Ngân hàng Nhà nước Việt Nam trong lĩnh vực quản lý, giám sát ngân hàng liên quan đến cắt giảm điều kiện kinh doanh, đơn giản hóa thủ tục hành chính', loai_van_ban: 'Thông tư', ngay_ban_hanh: '31/12/2025', ngay_co_hieu_luc: '15/02/2026', tinh_trang_hieu_luc: 'Còn hiệu lực', co_quan_ban_hanh: 'Ngân hàng Nhà nước Việt Nam'},
  {id: '112924', so_ky_hieu: '105/2016/TT-BTC', title: 'Thông tư số 105/2016/TT-BTC Hướng dẫn hoạt động đầu tư gián tiếp ra nước ngoài của tổ chức kinh doanh chứng khoán, quỹ đầu tư chứng khoán, công ty đầu tư chứng khoán và doanh nghỉệp kinh doanh bảo hỉểm', loai_van_ban: 'Thông tư', ngay_ban_hanh: '29/06/2016', ngay_co_hieu_luc: '15/08/2016', tinh_trang_hieu_luc: 'Hết hiệu lực một phần', co_quan_ban_hanh: 'Bộ Tài chính'},
  {id: '174218', so_ky_hieu: '62/2024/TT-NHNN', title: 'Thông tư số 62/2024/TT-NHNN Quy định điều kiện, hồ sơ, thủ tục chấp thuận việc tổ chức lại ngân hàng thương mại, tổ chức tín dụng phi ngân hàng', loai_van_ban: 'Thông tư', ngay_ban_hanh: '31/12/2024', ngay_co_hieu_luc: '17/02/2025', tinh_trang_hieu_luc: 'Hết hiệu lực một phần', co_quan_ban_hanh: 'Ngân hàng Nhà nước Việt Nam'},
  {id: '186888', so_ky_hieu: '62/2025/TT-NHNN', title: 'Thông tư số 62/2025/TT-NHNN Quy định về hệ thống kiểm soát nội bộ của tổ chức tín dụng là hợp tác xã, tổ chức tài chính vi mô', loai_van_ban: 'Thông tư', ngay_ban_hanh: '31/12/2025', ngay_co_hieu_luc: '01/01/2027', tinh_trang_hieu_luc: 'Chưa có hiệu lực', co_quan_ban_hanh: 'Ngân hàng Nhà nước Việt Nam'},
  {id: '6e689cd0-6f81-11f1-94d6-fd5d6d5ff793', so_ky_hieu: '52/VBHN-NHNN', title: 'Quy định hồ sơ, thủ tục cấp Giấy phép lần đầu của ngân hàng thương mại, chi nhánh ngân hàng nước ngoài, văn phòng đại diện nước ngoài', loai_van_ban: 'Văn bản hợp nhất', ngay_ban_hanh: '21/05/2026', ngay_co_hieu_luc: null, tinh_trang_hieu_luc: 'Chưa xác định', co_quan_ban_hanh: 'Ngân hàng Nhà nước Việt Nam'},
  {id: '185630', so_ky_hieu: '63/2025/TT-NHNN', title: 'Thông tư số 63/2025/TT-NHNN Sửa đổi, bổ sung một số điều của một số Thông tư về quỹ tín dụng nhân dân', loai_van_ban: 'Thông tư', ngay_ban_hanh: '31/12/2025', ngay_co_hieu_luc: '16/02/2026', tinh_trang_hieu_luc: 'Còn hiệu lực', co_quan_ban_hanh: 'Ngân hàng Nhà nước Việt Nam'},
  {id: '117310', so_ky_hieu: '41/2016/TT-NHNN', title: 'Thông tư số 41/2016/TT-NHNN Quy định tỷ lệ an toàn vốn đối với ngân hàng, chi nhánh ngân hàng nước ngoài', loai_van_ban: 'Thông tư', ngay_ban_hanh: '30/12/2016', ngay_co_hieu_luc: '01/01/2020', tinh_trang_hieu_luc: 'Hết hiệu lực một phần', co_quan_ban_hanh: 'Ngân hàng Nhà nước Việt Nam'},
  {id: '166269', so_ky_hieu: '17/2023/QH15', title: 'Luật Hợp tác xã số 17/2023/QH15', loai_van_ban: 'Luật', ngay_ban_hanh: '20/06/2023', ngay_co_hieu_luc: '01/07/2024', tinh_trang_hieu_luc: 'Còn hiệu lực', co_quan_ban_hanh: 'Quốc hội'},
  {id: '177271', so_ky_hieu: '01/2025/TT-NHNN', title: 'Thông tư số 01/2025/TT-NHNN Quy định về cấp Giấy phép lần đầu, cấp đổi Giấy phép của quỹ tín dụng nhân dân', loai_van_ban: 'Thông tư', ngay_ban_hanh: '29/04/2025', ngay_co_hieu_luc: '15/06/2025', tinh_trang_hieu_luc: 'Hết hiệu lực một phần', co_quan_ban_hanh: 'Ngân hàng Nhà nước Việt Nam'},
  {id: '44209', so_ky_hieu: '01/2014/TT-NHNN', title: 'Thông tư số 01/2014/TT-NHNN Quy định về giao nhận, bảo quản, vận chuyển tiền mặt, tài sản quý, giấy tờ có giá', loai_van_ban: 'Thông tư', ngay_ban_hanh: '06/01/2014', ngay_co_hieu_luc: '20/02/2014', tinh_trang_hieu_luc: 'Hết hiệu lực một phần', co_quan_ban_hanh: 'Ngân hàng Nhà nước Việt Nam'},
  {id: '25692', so_ky_hieu: '46/2010/QH12', title: 'Ngân hàng Nhà nước Việt Nam', loai_van_ban: 'Luật', ngay_ban_hanh: '16/06/2010', ngay_co_hieu_luc: '01/01/2011', tinh_trang_hieu_luc: 'Hết hiệu lực một phần', co_quan_ban_hanh: 'Quốc hội'}
] AS row
MERGE (d:Document {so_ky_hieu: row.so_ky_hieu})
SET d.id = row.id,
    d.title = row.title,
    d.loai_van_ban = row.loai_van_ban,
    d.ngay_ban_hanh = row.ngay_ban_hanh,
    d.ngay_co_hieu_luc = row.ngay_co_hieu_luc,
    d.tinh_trang_hieu_luc = row.tinh_trang_hieu_luc,
    d.co_quan_ban_hanh = row.co_quan_ban_hanh
RETURN count(d) AS so_document;

// BƯỚC 8.3 — CoQuan nodes (4 entity)
UNWIND [
  {entity_id: 'COQ_001', canonical_name: 'Bộ Tài chính'},
  {entity_id: 'COQ_002', canonical_name: 'Chính phủ'},
  {entity_id: 'COQ_003', canonical_name: 'Ngân hàng Nhà nước Việt Nam'},
  {entity_id: 'COQ_004', canonical_name: 'Quốc hội'}
] AS row
MERGE (n:CoQuan {canonical_name: row.canonical_name})
SET n.entity_id = row.entity_id
RETURN count(n) AS so_coquan;

// BƯỚC 8.3 — NguoiKy nodes (14 entity)
UNWIND [
  {entity_id: 'NGU_116', canonical_name: 'Lê Minh Khái'},
  {entity_id: 'NGU_117', canonical_name: 'Nguyễn Phú Trọng'},
  {entity_id: 'NGU_118', canonical_name: 'Nguyễn Tấn Dũng'},
  {entity_id: 'NGU_119', canonical_name: 'Nguyễn Xuân Phúc'},
  {entity_id: 'NGU_120', canonical_name: 'Nguyễn Đồng Tiến'},
  {entity_id: 'NGU_121', canonical_name: 'Nguyễn Đức Chi'},
  {entity_id: 'NGU_122', canonical_name: 'Phạm Thanh Hà'},
  {entity_id: 'NGU_123', canonical_name: 'Trần Minh Tuấn'},
  {entity_id: 'NGU_124', canonical_name: 'Trần Xuân Hà'},
  {entity_id: 'NGU_125', canonical_name: 'Tạ Anh Tuấn'},
  {entity_id: 'NGU_126', canonical_name: 'Vương Đình Huệ'},
  {entity_id: 'NGU_127', canonical_name: 'Đoàn Thái Sơn'},
  {entity_id: 'NGU_128', canonical_name: 'Đào Minh Tú'},
  {entity_id: 'NGU_129', canonical_name: 'Đỗ Hoàng Anh Tuấn'}
] AS row
MERGE (n:NguoiKy {canonical_name: row.canonical_name})
SET n.entity_id = row.entity_id
RETURN count(n) AS so_nguoiky;

// BƯỚC 8.3 — DoiTuongApDung nodes (98 entity)
UNWIND [
  {entity_id: 'DOI_005', canonical_name: 'Bên mua bảo hiểm'},
  {entity_id: 'DOI_006', canonical_name: 'Bộ, cơ quan ngang bộ, cơ quan thuộc Chính phủ'},
  {entity_id: 'DOI_007', canonical_name: 'Chi nhánh doanh nghiệp bảo hiểm phi nhân thọ nước ngoài'},
  {entity_id: 'DOI_008', canonical_name: 'Chi nhánh doanh nghiệp tái bảo hiểm nước ngoài'},
  {entity_id: 'DOI_009', canonical_name: 'Chi nhánh ngân hàng nước ngoài'},
  {entity_id: 'DOI_010', canonical_name: 'Chi nhánh nước ngoài'},
  {entity_id: 'DOI_011', canonical_name: 'Cá nhân có quốc tịch Việt Nam thuộc đối tượng được tham gia chương trình thưởng cổ phiếu phát hành ở nước ngoài'},
  {entity_id: 'DOI_012', canonical_name: 'Công ty chứng khoán, công ty quản lý quỹ đầu tư chứng khoán, chi nhánh, văn phòng đại diện công ty chứng khoán, công ty quản lý quỹ nước ngoài tại Việt Nam, công ty đầu tư chứng khoán'},
  {entity_id: 'DOI_013', canonical_name: 'Công ty tài chính chuyên ngành'},
  {entity_id: 'DOI_014', canonical_name: 'Công ty tài chính tổng hợp'},
  {entity_id: 'DOI_015', canonical_name: 'Công ty đại chúng'},
  {entity_id: 'DOI_016', canonical_name: 'Công ty đầu tư chứng khoán'},
  {entity_id: 'DOI_017', canonical_name: 'Cơ quan quản lý nhà nước tham gia quản lý hoạt động đầu tư gián tiếp ra nước ngoài theo quy định tại Nghị định này'},
  {entity_id: 'DOI_018', canonical_name: 'Cơ quan quản lý nhà nước về hoạt động kinh doanh bảo hiểm'},
  {entity_id: 'DOI_019', canonical_name: 'Cơ quan, tổ chức, cá nhân có liên quan đến hoạt động đầu tư gián tiếp ra nước ngoài'},
  {entity_id: 'DOI_020', canonical_name: 'Cơ quan, tổ chức, cá nhân có liên quan đến thành lập, tổ chức quản lý, tổ chức lại, giải thể, phá sản và hoạt động có liên quan của tổ hợp tác, hợp tác xã, liên hiệp hợp tác xã'},
  {entity_id: 'DOI_021', canonical_name: 'Cơ quan, tổ chức, cá nhân có liên quan đến việc thành lập, tổ chức, hoạt động, can thiệp sớm, kiểm soát đặc biệt, tổ chức lại, giải thể, phá sản tổ chức tín dụng'},
  {entity_id: 'DOI_022', canonical_name: 'Cổ đông, nhà đầu tư là tổ chức'},
  {entity_id: 'DOI_023', canonical_name: 'Doanh nghiệp'},
  {entity_id: 'DOI_024', canonical_name: 'Doanh nghiệp bảo hiểm'},
  {entity_id: 'DOI_025', canonical_name: 'Doanh nghiệp bảo hiểm nhân thọ'},
  {entity_id: 'DOI_026', canonical_name: 'Doanh nghiệp bảo hiểm phi nhân thọ'},
  {entity_id: 'DOI_027', canonical_name: 'Doanh nghiệp bảo hiểm sức khỏe'},
  {entity_id: 'DOI_028', canonical_name: 'Doanh nghiệp không thuộc quy định tại khoản 1 Điều này'},
  {entity_id: 'DOI_029', canonical_name: 'Doanh nghiệp kinh doanh bảo hiểm'},
  {entity_id: 'DOI_030', canonical_name: 'Doanh nghiệp kiểm toán, chi nhánh doanh nghiệp kiểm toán nước ngoài tại Việt Nam'},
  {entity_id: 'DOI_031', canonical_name: 'Doanh nghiệp môi giới bảo hiểm'},
  {entity_id: 'DOI_032', canonical_name: 'Doanh nghiệp nhà nước, công ty trách nhiệm hữu hạn một thành viên do doanh nghiệp nhà nước nắm giữ 100% vốn điều lệ, đơn vị sự nghiệp công lập cổ phần hóa dưới hình thức chào bán chứng khoán ra công chúng'},
  {entity_id: 'DOI_033', canonical_name: 'Doanh nghiệp quy định tại khoản 1 Điều 10 Nghị định số 05/2019/NĐ-CP'},
  {entity_id: 'DOI_034', canonical_name: 'Doanh nghiệp tái bảo hiểm'},
  {entity_id: 'DOI_035', canonical_name: 'Doanh nghiệp, cơ quan nhà nước, đơn vị sự nghiệp công lập quy định tại Điều 8, Điều 9, Điều 10 Nghị định số 05/2019/NĐ-CP'},
  {entity_id: 'DOI_036', canonical_name: 'Khách hàng trong quan hệ giao dịch tiền mặt, tài sản quý, giấy tờ có giá với Ngân hàng Nhà nước, tổ chức tín dụng, chi nhánh ngân hàng nước ngoài'},
  {entity_id: 'DOI_037', canonical_name: 'Kiểm toán viên đăng ký hành nghề tại doanh nghiệp kiểm toán, chi nhánh doanh nghiệp kiểm toán nước ngoài tại Việt Nam'},
  {entity_id: 'DOI_038', canonical_name: 'Ngân hàng 100% vốn nước ngoài'},
  {entity_id: 'DOI_039', canonical_name: 'Ngân hàng Nhà nước Việt Nam'},
  {entity_id: 'DOI_040', canonical_name: 'Ngân hàng hợp tác xã'},
  {entity_id: 'DOI_041', canonical_name: 'Ngân hàng liên doanh'},
  {entity_id: 'DOI_042', canonical_name: 'Ngân hàng thương mại'},
  {entity_id: 'DOI_043', canonical_name: 'Ngân hàng thương mại cổ phần'},
  {entity_id: 'DOI_044', canonical_name: 'Ngân hàng thương mại nhà nước'},
  {entity_id: 'DOI_045', canonical_name: 'Ngân hàng thương mại, chi nhánh ngân hàng nước ngoài tại Việt Nam thực hiện hoạt động lưu ký, bù trừ, thanh toán giao dịch chứng khoán, ngân hàng giám sát'},
  {entity_id: 'DOI_046', canonical_name: 'Người thụ hưởng'},
  {entity_id: 'DOI_047', canonical_name: 'Người được bảo hiểm'},
  {entity_id: 'DOI_048', canonical_name: 'Nhà máy in tiền Quốc gia'},
  {entity_id: 'DOI_049', canonical_name: 'Quỹ tín dụng nhân dân'},
  {entity_id: 'DOI_050', canonical_name: 'Quỹ đầu tư chứng khoán'},
  {entity_id: 'DOI_051', canonical_name: 'Sở giao dịch chứng khoán Việt Nam và công ty con'},
  {entity_id: 'DOI_052', canonical_name: 'Thành viên của tổ hợp tác, hợp tác xã, liên hiệp hợp tác xã'},
  {entity_id: 'DOI_053', canonical_name: 'Tổ chức cá nhân có liên quan trong hoạt động kiểm toán nội bộ của các đơn vị này'},
  {entity_id: 'DOI_054', canonical_name: 'Tổ chức khác hoạt động trên thị trường chứng khoán hoặc có liên quan đến hoạt động về chứng khoán và thị trường chứng khoán'},
  {entity_id: 'DOI_055', canonical_name: 'Tổ chức kinh doanh chứng khoán'},
  {entity_id: 'DOI_056', canonical_name: 'Tổ chức kinh tế có vốn đầu tư nước ngoài (thuộc đối tượng quy định tại Khoản 1 Điều 23 Luật Đầu tư)'},
  {entity_id: 'DOI_057', canonical_name: 'Tổ chức kinh tế theo quy định tại Khoản 16 Điều 3 Luật Đầu tư'},
  {entity_id: 'DOI_058', canonical_name: 'Tổ chức kiểm toán được chấp thuận'},
  {entity_id: 'DOI_059', canonical_name: 'Tổ chức mà Nhà nước sở hữu 100% vốn điều lệ có chức năng mua, bán, xử lý nợ'},
  {entity_id: 'DOI_060', canonical_name: 'Tổ chức niêm yết, tổ chức đăng ký giao dịch'},
  {entity_id: 'DOI_061', canonical_name: 'Tổ chức phát hành'},
  {entity_id: 'DOI_062', canonical_name: 'Tổ chức tài chính vi mô'},
  {entity_id: 'DOI_063', canonical_name: 'Tổ chức tín dụng'},
  {entity_id: 'DOI_064', canonical_name: 'Tổ chức tín dụng là hợp tác xã bao gồm ngân hàng hợp tác xã, quỹ tín dụng nhân dân'},
  {entity_id: 'DOI_065', canonical_name: 'Tổ chức tín dụng phi ngân hàng bao gồm công ty tài chính tổng hợp và công ty tài chính chuyên ngành'},
  {entity_id: 'DOI_066', canonical_name: 'Tổ chức tín dụng, chi nhánh ngân hàng nước ngoài'},
  {entity_id: 'DOI_067', canonical_name: 'Tổ chức tư vấn chào bán, phát hành, tổ chức bảo lãnh phát hành'},
  {entity_id: 'DOI_068', canonical_name: 'Tổ chức tương hỗ cung cấp bảo hiểm vi mô'},
  {entity_id: 'DOI_069', canonical_name: 'Tổ chức và cá nhân có liên quan đến hoạt động kinh doanh bảo hiểm'},
  {entity_id: 'DOI_070', canonical_name: 'Tổ chức xã hội - nghề nghiệp về chứng khoán'},
  {entity_id: 'DOI_071', canonical_name: 'Tổ chức, cá nhân Việt Nam và tổ chức, cá nhân nước ngoài'},
  {entity_id: 'DOI_072', canonical_name: 'Tổ chức, cá nhân cung cấp dịch vụ phụ trợ bảo hiểm'},
  {entity_id: 'DOI_073', canonical_name: 'Tổ chức, cá nhân có liên quan đến hệ thống kiểm soát nội bộ của tổ chức tín dụng'},
  {entity_id: 'DOI_074', canonical_name: 'Tổ chức, cá nhân có liên quan đến hệ thống kiểm soát nội bộ và kiểm toán nội bộ của tổ chức tín dụng, chi nhánh ngân hàng nước ngoài'},
  {entity_id: 'DOI_075', canonical_name: 'Tổ chức, cá nhân có liên quan đến hồ sơ, thủ tục cấp Giấy phép lần đầu của ngân hàng thương mại, chi nhánh ngân hàng nước ngoài và văn phòng đại diện nước ngoài'},
  {entity_id: 'DOI_076', canonical_name: 'Tổ chức, cá nhân có liên quan đến phạm vi điều chỉnh quy định tại Điều 1 Thông tư này'},
  {entity_id: 'DOI_077', canonical_name: 'Tổ chức, cá nhân có liên quan đến quản trị, điều hành, tổ chức và hoạt động của quỹ tín dụng nhân dân'},
  {entity_id: 'DOI_078', canonical_name: 'Tổ chức, cá nhân có liên quan đến việc cấp Giấy phép lần đầu của tổ chức tín dụng phi ngân hàng'},
  {entity_id: 'DOI_079', canonical_name: 'Tổ chức, cá nhân có liên quan đến việc cấp Giấy phép lần đầu, cấp đổi Giấy phép của quỹ tín dụng nhân dân, cấp bản sao Giấy phép từ sổ gốc'},
  {entity_id: 'DOI_080', canonical_name: 'Tổ chức, cá nhân có liên quan đến việc tổ chức lại tổ chức tín dụng'},
  {entity_id: 'DOI_081', canonical_name: 'Tổ chức, cá nhân có liên quan đến việc đăng ký, quản lý và công khai danh sách kiểm toán viên hành nghề kiểm toán'},
  {entity_id: 'DOI_082', canonical_name: 'Tổ chức, cá nhân khác có liên quan'},
  {entity_id: 'DOI_083', canonical_name: 'Tổ chức, cá nhân khác có liên quan đến công việc thiết kế mẫu tiền, chế tạo bản in, khuôn đúc và in, đúc tiền'},
  {entity_id: 'DOI_084', canonical_name: 'Tổ chức, cá nhân khác có liên quan đến hoạt động kiểm toán nội bộ'},
  {entity_id: 'DOI_085', canonical_name: 'Tổ chức, cá nhân khác có liên quan đến hoạt động đầu tư gián tiếp ra nước ngoài'},
  {entity_id: 'DOI_086', canonical_name: 'Tổ hợp tác, hợp tác xã, liên hiệp hợp tác xã'},
  {entity_id: 'DOI_087', canonical_name: 'Tổng công ty lưu ký và bù trừ chứng khoán Việt Nam và công ty con'},
  {entity_id: 'DOI_088', canonical_name: 'Văn phòng đại diện của doanh nghiệp bảo hiểm nước ngoài, doanh nghiệp tái bảo hiểm nước ngoài, doanh nghiệp môi giới bảo hiểm nước ngoài, tập đoàn tài chính, bảo hiểm nước ngoài tại Việt Nam'},
  {entity_id: 'DOI_089', canonical_name: 'Văn phòng đại diện tại Việt Nam của tổ chức tín dụng nước ngoài, tổ chức nước ngoài khác có hoạt động ngân hàng'},
  {entity_id: 'DOI_090', canonical_name: 'chi nhánh doanh nghiệp kiểm toán nước ngoài tại Việt Nam'},
  {entity_id: 'DOI_091', canonical_name: 'doanh nghiệp kiểm toán'},
  {entity_id: 'DOI_092', canonical_name: 'kiểm toán viên'},
  {entity_id: 'DOI_093', canonical_name: 'kiểm toán viên hành nghề'},
  {entity_id: 'DOI_094', canonical_name: 'tổ chức nghề nghiệp về kiểm toán'},
  {entity_id: 'DOI_095', canonical_name: 'tổ chức tư vấn niêm yết, đăng ký giao dịch'},
  {entity_id: 'DOI_096', canonical_name: 'tổ chức đấu thầu, đại lý phát hành'},
  {entity_id: 'DOI_097', canonical_name: 'tổ chức, cá nhân khác có liên quan đến hoạt động kiểm toán độc lập'},
  {entity_id: 'DOI_098', canonical_name: 'Đơn vị có liên quan thuộc Ngân hàng Nhà nước'},
  {entity_id: 'DOI_099', canonical_name: 'Đơn vị sự nghiệp công lập'},
  {entity_id: 'DOI_100', canonical_name: 'Đại lý bảo hiểm'},
  {entity_id: 'DOI_101', canonical_name: 'đơn vị được kiểm toán'},
  {entity_id: 'DOI_102', canonical_name: 'Ủy ban nhân dân các tỉnh, thành phố trực thuộc trung ương'}
] AS row
MERGE (n:DoiTuongApDung {canonical_name: row.canonical_name})
SET n.entity_id = row.entity_id
RETURN count(n) AS so_doituongapdung;

// BƯỚC 8.3 — LinhVuc nodes (13 entity)
UNWIND [
  {entity_id: 'LIN_103', canonical_name: 'Bảo hiểm'},
  {entity_id: 'LIN_104', canonical_name: 'Chứng khoán'},
  {entity_id: 'LIN_105', canonical_name: 'Cục An toàn hệ thống các tổ chức tín dụng'},
  {entity_id: 'LIN_106', canonical_name: 'Hợp tác xã'},
  {entity_id: 'LIN_107', canonical_name: 'Kiểm toán'},
  {entity_id: 'LIN_108', canonical_name: 'Kế toán, kiểm toán'},
  {entity_id: 'LIN_109', canonical_name: 'Lao động, tiền lương, tiền công'},
  {entity_id: 'LIN_110', canonical_name: 'Phát hành và kho quỹ'},
  {entity_id: 'LIN_111', canonical_name: 'Quản lý dịch vụ tài chính và các quỹ tài chính'},
  {entity_id: 'LIN_112', canonical_name: 'Quản lý ngoại hối'},
  {entity_id: 'LIN_113', canonical_name: 'Thanh tra, giám sát ngân hàng'},
  {entity_id: 'LIN_114', canonical_name: 'Tín dụng'},
  {entity_id: 'LIN_115', canonical_name: 'Tổ chức và hoạt động Ngân hàng Nhà nước'}
] AS row
MERGE (n:LinhVuc {canonical_name: row.canonical_name})
SET n.entity_id = row.entity_id
RETURN count(n) AS so_linhvuc;

// BƯỚC 8.4 — [:BAN_HANH_BOI] (30 edge)
UNWIND [
  {source: '105/2016/TT-BTC', target: 'Bộ Tài chính', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Bộ Tài chính\''},
  {source: '01/2025/TT-NHNN', target: 'Ngân hàng Nhà nước Việt Nam', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Ngân hàng Nhà nước Việt Nam\''},
  {source: '63/2025/TT-NHNN', target: 'Ngân hàng Nhà nước Việt Nam', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Ngân hàng Nhà nước Việt Nam\''},
  {source: '69/2025/TT-NHNN', target: 'Ngân hàng Nhà nước Việt Nam', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Ngân hàng Nhà nước Việt Nam\''},
  {source: '62/2025/TT-NHNN', target: 'Ngân hàng Nhà nước Việt Nam', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Ngân hàng Nhà nước Việt Nam\''},
  {source: '44/2011/TT-NHNN', target: 'Ngân hàng Nhà nước Việt Nam', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Ngân hàng Nhà nước Việt Nam\''},
  {source: '37/2014/TT-NHNN', target: 'Ngân hàng Nhà nước Việt Nam', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Ngân hàng Nhà nước Việt Nam\''},
  {source: '52/VBHN-NHNN', target: 'Ngân hàng Nhà nước Việt Nam', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Ngân hàng Nhà nước Việt Nam\''},
  {source: '32/2024/QH15', target: 'Quốc hội', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Quốc hội\''},
  {source: '17/2023/QH15', target: 'Quốc hội', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Quốc hội\''},
  {source: '46/2010/QH12', target: 'Quốc hội', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Quốc hội\''},
  {source: '67/2011/QH12', target: 'Quốc hội', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Quốc hội\''},
  {source: '62/2024/TT-NHNN', target: 'Ngân hàng Nhà nước Việt Nam', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Ngân hàng Nhà nước Việt Nam\''},
  {source: '46/2023/NĐ-CP', target: 'Chính phủ', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Chính phủ\''},
  {source: '156/2020/NĐ-CP', target: 'Chính phủ', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Chính phủ\''},
  {source: '05/2019/NĐ-CP', target: 'Chính phủ', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Chính phủ\''},
  {source: '73/2016/NĐ-CP', target: 'Chính phủ', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Chính phủ\''},
  {source: '17/VBHN-BTC', target: 'Bộ Tài chính', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Bộ Tài chính\''},
  {source: '202/2012/TT-BTC', target: 'Bộ Tài chính', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Bộ Tài chính\''},
  {source: '08/2021/TT-BTC', target: 'Bộ Tài chính', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Bộ Tài chính\''},
  {source: '66/2020/TT-BTC', target: 'Bộ Tài chính', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Bộ Tài chính\''},
  {source: '56/2024/TT-NHNN', target: 'Ngân hàng Nhà nước Việt Nam', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Ngân hàng Nhà nước Việt Nam\''},
  {source: '57/2024/TT-NHNN', target: 'Ngân hàng Nhà nước Việt Nam', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Ngân hàng Nhà nước Việt Nam\''},
  {source: '43/2024/TT-NHNN', target: 'Ngân hàng Nhà nước Việt Nam', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Ngân hàng Nhà nước Việt Nam\''},
  {source: '29/2024/TT-NHNN', target: 'Ngân hàng Nhà nước Việt Nam', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Ngân hàng Nhà nước Việt Nam\''},
  {source: '27/2024/TT-NHNN', target: 'Ngân hàng Nhà nước Việt Nam', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Ngân hàng Nhà nước Việt Nam\''},
  {source: '22/2023/TT-NHNN', target: 'Ngân hàng Nhà nước Việt Nam', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Ngân hàng Nhà nước Việt Nam\''},
  {source: '41/2016/TT-NHNN', target: 'Ngân hàng Nhà nước Việt Nam', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Ngân hàng Nhà nước Việt Nam\''},
  {source: '135/2015/NĐ-CP', target: 'Chính phủ', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Chính phủ\''},
  {source: '01/2014/TT-NHNN', target: 'Ngân hàng Nhà nước Việt Nam', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: co_quan_ban_hanh = \'Ngân hàng Nhà nước Việt Nam\''}
] AS row
MATCH (s:Document {so_ky_hieu: row.source})
MATCH (t:CoQuan {canonical_name: row.target})
MERGE (s)-[r:BAN_HANH_BOI]->(t)
SET r.method = row.method, r.confidence = row.confidence, r.evidence = row.evidence
RETURN count(r) AS so_ban_hanh_boi;

// BƯỚC 8.4 — [:KY_BOI] (30 edge)
UNWIND [
  {source: '01/2014/TT-NHNN', target: 'Đào Minh Tú', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Đào Minh Tú\''},
  {source: '37/2014/TT-NHNN', target: 'Đào Minh Tú', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Đào Minh Tú\''},
  {source: '29/2024/TT-NHNN', target: 'Đào Minh Tú', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Đào Minh Tú\''},
  {source: '27/2024/TT-NHNN', target: 'Đào Minh Tú', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Đào Minh Tú\''},
  {source: '52/VBHN-NHNN', target: 'Đoàn Thái Sơn', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Đoàn Thái Sơn\''},
  {source: '63/2025/TT-NHNN', target: 'Đoàn Thái Sơn', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Đoàn Thái Sơn\''},
  {source: '69/2025/TT-NHNN', target: 'Đoàn Thái Sơn', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Đoàn Thái Sơn\''},
  {source: '62/2025/TT-NHNN', target: 'Đoàn Thái Sơn', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Đoàn Thái Sơn\''},
  {source: '01/2025/TT-NHNN', target: 'Đoàn Thái Sơn', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Đoàn Thái Sơn\''},
  {source: '62/2024/TT-NHNN', target: 'Đoàn Thái Sơn', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Đoàn Thái Sơn\''},
  {source: '46/2010/QH12', target: 'Nguyễn Phú Trọng', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Nguyễn Phú Trọng\''},
  {source: '46/2023/NĐ-CP', target: 'Lê Minh Khái', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Lê Minh Khái\''},
  {source: '105/2016/TT-BTC', target: 'Trần Xuân Hà', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Trần Xuân Hà\''},
  {source: '44/2011/TT-NHNN', target: 'Trần Minh Tuấn', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Trần Minh Tuấn\''},
  {source: '17/VBHN-BTC', target: 'Nguyễn Đức Chi', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Nguyễn Đức Chi\''},
  {source: '43/2024/TT-NHNN', target: 'Phạm Thanh Hà', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Phạm Thanh Hà\''},
  {source: '41/2016/TT-NHNN', target: 'Nguyễn Đồng Tiến', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Nguyễn Đồng Tiến\''},
  {source: '156/2020/NĐ-CP', target: 'Nguyễn Xuân Phúc', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Nguyễn Xuân Phúc\''},
  {source: '05/2019/NĐ-CP', target: 'Nguyễn Xuân Phúc', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Nguyễn Xuân Phúc\''},
  {source: '73/2016/NĐ-CP', target: 'Nguyễn Xuân Phúc', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Nguyễn Xuân Phúc\''},
  {source: '56/2024/TT-NHNN', target: 'Đoàn Thái Sơn', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Đoàn Thái Sơn\''},
  {source: '57/2024/TT-NHNN', target: 'Đoàn Thái Sơn', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Đoàn Thái Sơn\''},
  {source: '22/2023/TT-NHNN', target: 'Đoàn Thái Sơn', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Đoàn Thái Sơn\''},
  {source: '17/2023/QH15', target: 'Vương Đình Huệ', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Vương Đình Huệ\''},
  {source: '32/2024/QH15', target: 'Vương Đình Huệ', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Vương Đình Huệ\''},
  {source: '08/2021/TT-BTC', target: 'Tạ Anh Tuấn', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Tạ Anh Tuấn\''},
  {source: '202/2012/TT-BTC', target: 'Trần Xuân Hà', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Trần Xuân Hà\''},
  {source: '67/2011/QH12', target: 'Nguyễn Phú Trọng', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Nguyễn Phú Trọng\''},
  {source: '135/2015/NĐ-CP', target: 'Nguyễn Tấn Dũng', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: nguoi_ky = \'Nguyễn Tấn Dũng\''},
  {source: '66/2020/TT-BTC', target: 'Đỗ Hoàng Anh Tuấn', method: 'claude_llm', confidence: 0.9, evidence: 'KT. BỘ TRƯỞNG THỨ TRƯỞNG (Đã ký) Đỗ Hoàng Anh Tuấn'}
] AS row
MATCH (s:Document {so_ky_hieu: row.source})
MATCH (t:NguoiKy {canonical_name: row.target})
MERGE (s)-[r:KY_BOI]->(t)
SET r.method = row.method, r.confidence = row.confidence, r.evidence = row.evidence
RETURN count(r) AS so_ky_boi;

// BƯỚC 8.4 — [:THUOC_LINH_VUC] (30 edge)
UNWIND [
  {source: '37/2014/TT-NHNN', target: 'Phát hành và kho quỹ', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Phát hành và kho quỹ\''},
  {source: '01/2014/TT-NHNN', target: 'Phát hành và kho quỹ', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Phát hành và kho quỹ\''},
  {source: '44/2011/TT-NHNN', target: 'Kế toán, kiểm toán', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Kế toán, kiểm toán\''},
  {source: '05/2019/NĐ-CP', target: 'Kế toán, kiểm toán', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Kế toán, kiểm toán\''},
  {source: '08/2021/TT-BTC', target: 'Kế toán, kiểm toán', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Kế toán, kiểm toán\''},
  {source: '66/2020/TT-BTC', target: 'Kế toán, kiểm toán', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Kế toán, kiểm toán\''},
  {source: '202/2012/TT-BTC', target: 'Quản lý dịch vụ tài chính và các quỹ tài chính', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Quản lý dịch vụ tài chính và các quỹ tài chính\''},
  {source: '105/2016/TT-BTC', target: 'Chứng khoán', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Chứng khoán\''},
  {source: '63/2025/TT-NHNN', target: 'Lao động, tiền lương, tiền công', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Lao động, tiền lương, tiền công\''},
  {source: '62/2025/TT-NHNN', target: 'Cục An toàn hệ thống các tổ chức tín dụng', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Cục An toàn hệ thống các tổ chức tín dụng\''},
  {source: '69/2025/TT-NHNN', target: 'Cục An toàn hệ thống các tổ chức tín dụng', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Cục An toàn hệ thống các tổ chức tín dụng\''},
  {source: '01/2025/TT-NHNN', target: 'Cục An toàn hệ thống các tổ chức tín dụng', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Cục An toàn hệ thống các tổ chức tín dụng\''},
  {source: '17/VBHN-BTC', target: 'Chứng khoán', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Chứng khoán\''},
  {source: '156/2020/NĐ-CP', target: 'Chứng khoán', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Chứng khoán\''},
  {source: '27/2024/TT-NHNN', target: 'Thanh tra, giám sát ngân hàng', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Thanh tra, giám sát ngân hàng\''},
  {source: '135/2015/NĐ-CP', target: 'Quản lý ngoại hối', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Quản lý ngoại hối\''},
  {source: '41/2016/TT-NHNN', target: 'Thanh tra, giám sát ngân hàng', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Thanh tra, giám sát ngân hàng\''},
  {source: '22/2023/TT-NHNN', target: 'Thanh tra, giám sát ngân hàng', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Thanh tra, giám sát ngân hàng\''},
  {source: '57/2024/TT-NHNN', target: 'Thanh tra, giám sát ngân hàng', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Thanh tra, giám sát ngân hàng\''},
  {source: '73/2016/NĐ-CP', target: 'Bảo hiểm', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Bảo hiểm\''},
  {source: '46/2023/NĐ-CP', target: 'Bảo hiểm', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Bảo hiểm\''},
  {source: '32/2024/QH15', target: 'Tín dụng', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Tín dụng\''},
  {source: '52/VBHN-NHNN', target: 'Thanh tra, giám sát ngân hàng', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Thanh tra, giám sát ngân hàng\''},
  {source: '62/2024/TT-NHNN', target: 'Thanh tra, giám sát ngân hàng', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Thanh tra, giám sát ngân hàng\''},
  {source: '43/2024/TT-NHNN', target: 'Quản lý ngoại hối', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Quản lý ngoại hối\''},
  {source: '56/2024/TT-NHNN', target: 'Thanh tra, giám sát ngân hàng', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Thanh tra, giám sát ngân hàng\''},
  {source: '29/2024/TT-NHNN', target: 'Thanh tra, giám sát ngân hàng', method: 'metadata_original', confidence: 1.0, evidence: 'metadata.csv: linh_vuc = \'Thanh tra, giám sát ngân hàng\''},
  {source: '67/2011/QH12', target: 'Kiểm toán', method: 'claude_llm', confidence: 0.9, evidence: 'LUẬT Kiểm toán độc lập'},
  {source: '17/2023/QH15', target: 'Hợp tác xã', method: 'claude_llm', confidence: 0.6, evidence: 'LUẬT HỢP TÁC XÃ'},
  {source: '46/2010/QH12', target: 'Tổ chức và hoạt động Ngân hàng Nhà nước', method: 'claude_llm', confidence: 0.5, evidence: 'LUẬT Ngân hàng Nhà nước Việt Nam'}
] AS row
MATCH (s:Document {so_ky_hieu: row.source})
MATCH (t:LinhVuc {canonical_name: row.target})
MERGE (s)-[r:THUOC_LINH_VUC]->(t)
SET r.method = row.method, r.confidence = row.confidence, r.evidence = row.evidence
RETURN count(r) AS so_thuoc_linh_vuc;

// BƯỚC 8.4 — [:THAM_CHIEU] (15 edge)
UNWIND [
  {source: '37/2014/TT-NHNN', target: '46/2010/QH12', method: 'rule', confidence: 0.95, evidence: 'Căn cứ Luật Ngân hàng Nhà nước Việt Nam số 46/2010/QH12;'},
  {source: '41/2016/TT-NHNN', target: '46/2010/QH12', method: 'rule', confidence: 0.95, evidence: 'Căn cứ Luật Ngân hàng Nhà nước Việt Nam số 46/2010/QH12 ngày 16 tháng 6 năm 2010;'},
  {source: '01/2014/TT-NHNN', target: '46/2010/QH12', method: 'rule', confidence: 0.95, evidence: 'Căn cứ Luật Ngân hàng Nhà nước Việt Nam số 46/2010/QH12 ngày 16 tháng 6 năm 2010;'},
  {source: '63/2025/TT-NHNN', target: '32/2024/QH15', method: 'rule', confidence: 0.95, evidence: 'Căn cứ Luật Các tổ chức tín dụng số 32/2024/QH15 được sửa đổi, bổ sung bởi Luật số 96/2025/QH15;'},
  {source: '69/2025/TT-NHNN', target: '46/2010/QH12', method: 'rule', confidence: 0.95, evidence: 'Căn cứ Luật Ngân hàng Nhà nước Việt Nam số 46/2010/QH12;'},
  {source: '69/2025/TT-NHNN', target: '32/2024/QH15', method: 'rule', confidence: 0.95, evidence: 'Căn cứ Luật Các tổ chức tín dụng số 32/2024/QH15 được sửa đổi, bổ sung bởi Luật số 96/2025/QH15;'},
  {source: '08/2021/TT-BTC', target: '05/2019/NĐ-CP', method: 'rule', confidence: 0.95, evidence: 'Căn cứ Nghị định 05/2019/NĐ-CP ngày 22 tháng 01 năm 2019 của Chính phủ về kiểm toán nội bộ;'},
  {source: '105/2016/TT-BTC', target: '135/2015/NĐ-CP', method: 'rule', confidence: 0.95, evidence: 'Căn cứ Nghị định số 135/2015/NĐ-CP ngày 31 tháng 12 năm 2015 của Chính phủ quy định về đầu tư gián tiếp ra nước ngoài;'},
  {source: '62/2025/TT-NHNN', target: '32/2024/QH15', method: 'rule', confidence: 0.95, evidence: 'Căn cứ Luật Các tổ chức tín dụng số 32/2024/QH15 được sửa đổi, bổ sung bởi Luật số 96/2025/QH15;'},
  {source: '62/2025/TT-NHNN', target: '46/2010/QH12', method: 'rule', confidence: 0.95, evidence: 'Căn cứ Luật Ngân hàng Nhà nước Việt Nam số 46/2010/QH12;'},
  {source: '63/2025/TT-NHNN', target: '17/2023/QH15', method: 'rule', confidence: 0.95, evidence: 'Căn cứ Luật Hợp tác xã số 17/2023/QH15;'},
  {source: '63/2025/TT-NHNN', target: '46/2010/QH12', method: 'rule', confidence: 0.95, evidence: 'Căn cứ Luật Ngân hàng Nhà nước Việt Nam số 46/2010/QH12;'},
  {source: '44/2011/TT-NHNN', target: '46/2010/QH12', method: 'rule', confidence: 0.95, evidence: 'Căn cứ Luật Ngân hàng Nhà nước Việt Nam số 46/2010/QH12 ngày 16 tháng 6 năm 2010;'},
  {source: '66/2020/TT-BTC', target: '05/2019/NĐ-CP', method: 'rule', confidence: 0.95, evidence: 'Căn cứ Nghị định số 05/2019/NĐ-CP ngày 22 thảng 01 năm 2019 của Chính phủ về kiếm toán nội bộ;'},
  {source: '202/2012/TT-BTC', target: '67/2011/QH12', method: 'rule', confidence: 0.95, evidence: 'Căn cứ Luật Kiểm toán độc lập số 67/2011/QH12 ngày 29 tháng 3 năm 2011;'}
] AS row
MATCH (s:Document {so_ky_hieu: row.source})
MATCH (t:Document {so_ky_hieu: row.target})
MERGE (s)-[r:THAM_CHIEU]->(t)
SET r.method = row.method, r.confidence = row.confidence, r.evidence = row.evidence
RETURN count(r) AS so_tham_chieu;

// BƯỚC 8.4 — [:SUA_DOI_BO_SUNG] (7 edge)
UNWIND [
  {source: '43/2024/TT-NHNN', target: '01/2014/TT-NHNN', method: 'rule', confidence: 0.9, evidence: 'Sửa đổi, bổ sung một số điều của Thông tư số 01/2014/TT-NHNN ngày 10'},
  {source: '17/VBHN-BTC', target: '156/2020/NĐ-CP', method: 'rule', confidence: 0.9, evidence: 'Chính phủ sửa đổi, bổ sung một số điều của Nghị định số 156/2020/NĐ-CP ngày 31 tháng 12 năm 2020 của Chính phủ quy định xử phạt vi phạm hành chính trong lĩnh vự'},
  {source: '69/2025/TT-NHNN', target: '62/2024/TT-NHNN', method: 'rule', confidence: 0.9, evidence: 'SỬA ĐỔI, BỔ SUNG MỘT SỐ ĐIỀU CỦA THÔNG TƯ SỐ 62/2024/TT-NHNN CỦA THỐNG ĐỐC NGÂN HÀNG NHÀ NƯỚC VIỆT NAM QUY ĐỊNH VỀ ĐIỀU KIỆN, HỒ SƠ, THỦ TỤC CHẤP THUẬN VIỆC TỔ '},
  {source: '46/2023/NĐ-CP', target: '73/2016/NĐ-CP', method: 'rule', confidence: 0.9, evidence: 'm và Luật sửa đổi, bổ sung một số điều của Luật Kinh doanh bảo hiểm, trừ các Điều 10, 61, 62, 63, 64, 65, 66, 67. Các Điều 10, 61, 62, 63, 64, 65, 66, 67 của Ng'},
  {source: '63/2025/TT-NHNN', target: '29/2024/TT-NHNN', method: 'rule', confidence: 0.9, evidence: 'SỬA ĐỔI, BỔ SUNG MỘT SỐ ĐIỀU CỦA THÔNG TƯ SỐ 29/2024/TT-NHNN QUY ĐỊNH VỀ QUỸ TÍN DỤNG NHÂN DÂN'},
  {source: '63/2025/TT-NHNN', target: '01/2025/TT-NHNN', method: 'rule', confidence: 0.9, evidence: 'SỬA ĐỔI, BỔ SUNG MỘT SỐ ĐIỀU CỦA THÔNG TƯ SỐ 01/2025/TT-NHNN QUY ĐỊNH VỀ CẤP GIẤY PHÉP LẦN ĐẦU, CẤP ĐỔI GIẤY PHÉP CỦA QUỸ TÍN DỤNG NHÂN DÂN'},
  {source: '22/2023/TT-NHNN', target: '41/2016/TT-NHNN', method: 'rule', confidence: 0.9, evidence: 'Sửa đổi, bổ sung một số điều của Thông tư số 41/2016/TT-NHNN ngày 30 tháng 12 năm 2016 của Thống đốc Ngân hàng Nhà nước Việt Nam quy định tỷ lệ an toàn vốn đối '}
] AS row
MATCH (s:Document {so_ky_hieu: row.source})
MATCH (t:Document {so_ky_hieu: row.target})
MERGE (s)-[r:SUA_DOI_BO_SUNG]->(t)
SET r.method = row.method, r.confidence = row.confidence, r.evidence = row.evidence
RETURN count(r) AS so_sua_doi_bo_sung;

// BƯỚC 8.4 — [:THAY_THE_BOI] (1 edge)
UNWIND [
  {source: '44/2011/TT-NHNN', target: '62/2025/TT-NHNN', method: 'rule', confidence: 0.9, evidence: 'ng tư này bãi bỏ Thông tư số 44/2011/TT-NHNN ngày 29 tháng 12 năm 2011 của Thống đốc Ngân hàng Nhà nước Việt Nam quy định về hệ thống kiểm soát nội bộ và kiểm t'}
] AS row
MATCH (s:Document {so_ky_hieu: row.source})
MATCH (t:Document {so_ky_hieu: row.target})
MERGE (s)-[r:THAY_THE_BOI]->(t)
SET r.method = row.method, r.confidence = row.confidence, r.evidence = row.evidence
RETURN count(r) AS so_thay_the_boi;

// BƯỚC 8.4 — [:AP_DUNG_CHO] (56 edge)_phan1
UNWIND [
  {source: '17/VBHN-BTC', target: 'tổ chức tư vấn niêm yết, đăng ký giao dịch', method: 'metadata_original', confidence: 1.0, evidence: null},
  {source: '17/VBHN-BTC', target: 'tổ chức đấu thầu, đại lý phát hành', method: 'metadata_original', confidence: 1.0, evidence: null},
  {source: '17/VBHN-BTC', target: 'Tổng công ty lưu ký và bù trừ chứng khoán Việt Nam và công ty con', method: 'metadata_original', confidence: 1.0, evidence: null},
  {source: '17/VBHN-BTC', target: 'Tổ chức tư vấn chào bán, phát hành, tổ chức bảo lãnh phát hành', method: 'metadata_original', confidence: 1.0, evidence: null},
  {source: '17/VBHN-BTC', target: 'Tổ chức niêm yết, tổ chức đăng ký giao dịch', method: 'metadata_original', confidence: 1.0, evidence: null},
  {source: '17/VBHN-BTC', target: 'Sở giao dịch chứng khoán Việt Nam và công ty con', method: 'metadata_original', confidence: 1.0, evidence: null},
  {source: '135/2015/NĐ-CP', target: 'Cá nhân có quốc tịch Việt Nam thuộc đối tượng được tham gia chương trình thưởng cổ phiếu phát hành ở nước ngoài', method: 'claude_llm', confidence: 0.9, evidence: 'b) Cá nhân có quốc tịch Việt Nam thuộc đối tượng được tham gia chương trình thưởng cổ phiếu phát hành ở nước ngoài.'},
  {source: '44/2011/TT-NHNN', target: 'Chi nhánh ngân hàng nước ngoài', method: 'claude_llm', confidence: 0.9, evidence: '2. Chi nhánh ngân hàng nước ngoài.'},
  {source: '41/2016/TT-NHNN', target: 'Chi nhánh ngân hàng nước ngoài', method: 'claude_llm', confidence: 0.9, evidence: '2. Chi nhánh ngân hàng nước ngoài.'},
  {source: '32/2024/QH15', target: 'Chi nhánh ngân hàng nước ngoài', method: 'claude_llm', confidence: 0.9, evidence: '2. Chi nhánh ngân hàng nước ngoài.'},
  {source: '56/2024/TT-NHNN', target: 'Chi nhánh ngân hàng nước ngoài', method: 'claude_llm', confidence: 0.9, evidence: '2. Chi nhánh ngân hàng nước ngoài.'},
  {source: '05/2019/NĐ-CP', target: 'Bộ, cơ quan ngang bộ, cơ quan thuộc Chính phủ', method: 'claude_llm', confidence: 0.9, evidence: 'a) Các bộ, cơ quan ngang bộ, cơ quan thuộc Chính phủ;'},
  {source: '17/VBHN-BTC', target: 'Công ty đại chúng', method: 'claude_llm', confidence: 0.9, evidence: 'a) Công ty đại chúng;'},
  {source: '57/2024/TT-NHNN', target: 'Công ty tài chính tổng hợp', method: 'claude_llm', confidence: 0.9, evidence: '1. Công ty tài chính tổng hợp.'},
  {source: '57/2024/TT-NHNN', target: 'Công ty tài chính chuyên ngành', method: 'claude_llm', confidence: 0.9, evidence: '2. Công ty tài chính chuyên ngành.'},
  {source: '52/VBHN-NHNN', target: 'Chi nhánh ngân hàng nước ngoài', method: 'claude_llm', confidence: 0.9, evidence: '2. Chi nhánh ngân hàng nước ngoài.'},
  {source: '73/2016/NĐ-CP', target: 'Chi nhánh nước ngoài', method: 'claude_llm', confidence: 0.9, evidence: 'b) Chi nhánh nước ngoài;'},
  {source: '27/2024/TT-NHNN', target: 'Ngân hàng hợp tác xã', method: 'claude_llm', confidence: 0.9, evidence: '1. Ngân hàng hợp tác xã.'},
  {source: '62/2024/TT-NHNN', target: 'Ngân hàng thương mại', method: 'claude_llm', confidence: 0.9, evidence: 'a) Ngân hàng thương mại;'},
  {source: '52/VBHN-NHNN', target: 'Ngân hàng thương mại', method: 'claude_llm', confidence: 0.9, evidence: 'a) Ngân hàng thương mại;'},
  {source: '202/2012/TT-BTC', target: 'Kiểm toán viên đăng ký hành nghề tại doanh nghiệp kiểm toán, chi nhánh doanh nghiệp kiểm toán nước ngoài tại Việt Nam', method: 'claude_llm', confidence: 0.9, evidence: '1. Kiểm toán viên đăng ký hành nghề tại doanh nghiệp kiểm toán, chi nhánh doanh nghiệp kiểm toán nước ngoài tại Việt Nam.'},
  {source: '56/2024/TT-NHNN', target: 'Ngân hàng thương mại', method: 'claude_llm', confidence: 0.9, evidence: 'a) Ngân hàng thương mại;'},
  {source: '29/2024/TT-NHNN', target: 'Ngân hàng hợp tác xã', method: 'claude_llm', confidence: 0.9, evidence: '1. Ngân hàng hợp tác xã.'},
  {source: '202/2012/TT-BTC', target: 'Doanh nghiệp kiểm toán, chi nhánh doanh nghiệp kiểm toán nước ngoài tại Việt Nam', method: 'claude_llm', confidence: 0.9, evidence: '2. Doanh nghiệp kiểm toán, chi nhánh doanh nghiệp kiểm toán nước ngoài tại Việt Nam (sau đây gọi chung là doanh nghiệp kiểm toán).'},
  {source: '17/VBHN-BTC', target: 'Cổ đông, nhà đầu tư là tổ chức', method: 'claude_llm', confidence: 0.9, evidence: 'i) Cổ đông, nhà đầu tư là tổ chức;'},
  {source: '05/2019/NĐ-CP', target: 'Doanh nghiệp', method: 'claude_llm', confidence: 0.9, evidence: 'd) Các doanh nghiệp;'},
  {source: '73/2016/NĐ-CP', target: 'Doanh nghiệp bảo hiểm', method: 'claude_llm', confidence: 0.9, evidence: 'a) Doanh nghiệp bảo hiểm;'},
  {source: '46/2023/NĐ-CP', target: 'Cơ quan quản lý nhà nước về hoạt động kinh doanh bảo hiểm', method: 'claude_llm', confidence: 0.9, evidence: '4. Cơ quan quản lý nhà nước về hoạt động kinh doanh bảo hiểm.'},
  {source: '05/2019/NĐ-CP', target: 'Đơn vị sự nghiệp công lập', method: 'claude_llm', confidence: 0.9, evidence: 'c) Các đơn vị sự nghiệp công lập;'},
  {source: '37/2014/TT-NHNN', target: 'Đơn vị có liên quan thuộc Ngân hàng Nhà nước', method: 'claude_llm', confidence: 0.9, evidence: '1. Các đơn vị có liên quan thuộc Ngân hàng Nhà nước.'},
  {source: '135/2015/NĐ-CP', target: 'Tổ chức kinh tế theo quy định tại Khoản 16 Điều 3 Luật Đầu tư', method: 'claude_llm', confidence: 0.9, evidence: 'a) Tổ chức kinh tế theo quy định tại Khoản 16 Điều 3 Luật Đầu tư;'},
  {source: '27/2024/TT-NHNN', target: 'Quỹ tín dụng nhân dân', method: 'claude_llm', confidence: 0.9, evidence: '2. Quỹ tín dụng nhân dân.'},
  {source: '29/2024/TT-NHNN', target: 'Quỹ tín dụng nhân dân', method: 'claude_llm', confidence: 0.9, evidence: '2. Quỹ tín dụng nhân dân.'},
  {source: '01/2025/TT-NHNN', target: 'Quỹ tín dụng nhân dân', method: 'claude_llm', confidence: 0.9, evidence: '2. Quỹ tín dụng nhân dân.'},
  {source: '37/2014/TT-NHNN', target: 'Nhà máy in tiền Quốc gia', method: 'claude_llm', confidence: 0.9, evidence: '2. Nhà máy in tiền Quốc gia.'},
  {source: '17/VBHN-BTC', target: 'Tổ chức phát hành', method: 'claude_llm', confidence: 0.9, evidence: 'c) Tổ chức phát hành;'},
  {source: '62/2025/TT-NHNN', target: 'Tổ chức tài chính vi mô', method: 'claude_llm', confidence: 0.9, evidence: '2. Tổ chức tài chính vi mô.'},
  {source: '32/2024/QH15', target: 'Tổ chức tín dụng', method: 'claude_llm', confidence: 0.9, evidence: '1. Tổ chức tín dụng.'},
  {source: '44/2011/TT-NHNN', target: 'Tổ chức tín dụng', method: 'claude_llm', confidence: 0.9, evidence: '1. Tổ chức tín dụng.'},
  {source: '62/2025/TT-NHNN', target: 'Tổ chức tín dụng là hợp tác xã bao gồm ngân hàng hợp tác xã, quỹ tín dụng nhân dân', method: 'claude_llm', confidence: 0.9, evidence: '1. Tổ chức tín dụng là hợp tác xã bao gồm ngân hàng hợp tác xã, quỹ tín dụng nhân dân.'},
  {source: '01/2014/TT-NHNN', target: 'Tổ chức tín dụng, chi nhánh ngân hàng nước ngoài', method: 'claude_llm', confidence: 0.9, evidence: '2. Tổ chức tín dụng, chi nhánh ngân hàng nước ngoài.'},
  {source: '17/VBHN-BTC', target: 'Tổ chức xã hội - nghề nghiệp về chứng khoán', method: 'claude_llm', confidence: 0.9, evidence: 'l) Tổ chức xã hội - nghề nghiệp về chứng khoán;'},
  {source: '46/2023/NĐ-CP', target: 'Tổ chức và cá nhân có liên quan đến hoạt động kinh doanh bảo hiểm', method: 'claude_llm', confidence: 0.9, evidence: '5. Tổ chức và cá nhân có liên quan đến hoạt động kinh doanh bảo hiểm.'},
  {source: '17/VBHN-BTC', target: 'Tổ chức kiểm toán được chấp thuận', method: 'claude_llm', confidence: 0.9, evidence: 'đ) Tổ chức kiểm toán được chấp thuận;'},
  {source: '17/2023/QH15', target: 'Thành viên của tổ hợp tác, hợp tác xã, liên hiệp hợp tác xã', method: 'claude_llm', confidence: 0.9, evidence: '2. Thành viên của tổ hợp tác, hợp tác xã, liên hiệp hợp tác xã.'},
  {source: '17/2023/QH15', target: 'Tổ hợp tác, hợp tác xã, liên hiệp hợp tác xã', method: 'claude_llm', confidence: 0.9, evidence: '1. Tổ hợp tác, hợp tác xã, liên hiệp hợp tác xã.'},
  {source: '05/2019/NĐ-CP', target: 'Ủy ban nhân dân các tỉnh, thành phố trực thuộc trung ương', method: 'claude_llm', confidence: 0.9, evidence: 'b) Ủy ban nhân dân các tỉnh, thành phố trực thuộc trung ương;'},
  {source: '135/2015/NĐ-CP', target: 'Cơ quan quản lý nhà nước tham gia quản lý hoạt động đầu tư gián tiếp ra nước ngoài theo quy định tại Nghị định này', method: 'claude_llm', confidence: 0.85, evidence: '2. Các cơ quan quản lý nhà nước tham gia quản lý hoạt động đầu tư gián tiếp ra nước ngoài theo quy định tại Nghị định này.'},
  {source: '17/2023/QH15', target: 'Cơ quan, tổ chức, cá nhân có liên quan đến thành lập, tổ chức quản lý, tổ chức lại, giải thể, phá sản và hoạt động có liên quan của tổ hợp tác, hợp tác xã, liên hiệp hợp tác xã', method: 'claude_llm', confidence: 0.85, evidence: '3. Cơ quan, tổ chức, cá nhân có liên quan đến thành lập, tổ chức quản lý, tổ chức lại, giải thể, phá sản và hoạt động có liên quan của tổ hợp tác, hợp tác xã, l'},
  {source: '46/2023/NĐ-CP', target: 'Doanh nghiệp bảo hiểm nhân thọ', method: 'claude_llm', confidence: 0.85, evidence: 'Doanh nghiệp bảo hiểm phi nhân thọ, doanh nghiệp bảo hiểm nhân thọ, doanh nghiệp bảo hiểm sức khỏe (sau đây gọi là doanh nghiệp bảo hiểm), doanh nghiệp tái bảo '},
  {source: '17/VBHN-BTC', target: 'Công ty chứng khoán, công ty quản lý quỹ đầu tư chứng khoán, chi nhánh, văn phòng đại diện công ty chứng khoán, công ty quản lý quỹ nước ngoài tại Việt Nam, công ty đầu tư chứng khoán', method: 'claude_llm', confidence: 0.85, evidence: 'g) Công ty chứng khoán, công ty quản lý quỹ đầu tư chứng khoán, chi nhánh, văn phòng đại diện công ty chứng khoán, công ty quản lý quỹ nước ngoài tại Việt Nam, '},
  {source: '105/2016/TT-BTC', target: 'Công ty đầu tư chứng khoán', method: 'claude_llm', confidence: 0.85, evidence: 'Thông tư này áp dụng đối với tổ chức kinh doanh chứng khoán, quỹ đầu tư chứng khoán, công ty đầu tư chứng khoán, doanh nghiệp kinh doanh bảo hiểm và các cơ quan'},
  {source: '46/2023/NĐ-CP', target: 'Bên mua bảo hiểm', method: 'claude_llm', confidence: 0.85, evidence: '3. Bên mua bảo hiểm, người được bảo hiểm, người thụ hưởng'},
  {source: '66/2020/TT-BTC', target: 'Doanh nghiệp quy định tại khoản 1 Điều 10 Nghị định số 05/2019/NĐ-CP', method: 'claude_llm', confidence: 0.85, evidence: 'Thông tư này áp dụng đối với các doanh nghiệp quy định tại khoản 1 Điều 10 Nghị định số 05/2019/NĐ-CP ngày 22 tháng 01 năm 2019 của Chính phủ về kiếm toán nội b'},
  {source: '105/2016/TT-BTC', target: 'Doanh nghiệp kinh doanh bảo hiểm', method: 'claude_llm', confidence: 0.85, evidence: 'Thông tư này áp dụng đối với tổ chức kinh doanh chứng khoán, quỹ đầu tư chứng khoán, công ty đầu tư chứng khoán, doanh nghiệp kinh doanh bảo hiểm và các cơ quan'},
  {source: '46/2023/NĐ-CP', target: 'Đại lý bảo hiểm', method: 'claude_llm', confidence: 0.85, evidence: 'Doanh nghiệp bảo hiểm phi nhân thọ, doanh nghiệp bảo hiểm nhân thọ, doanh nghiệp bảo hiểm sức khỏe (sau đây gọi là doanh nghiệp bảo hiểm), doanh nghiệp tái bảo '}
] AS row
MATCH (s:Document {so_ky_hieu: row.source})
MATCH (t:DoiTuongApDung {canonical_name: row.target})
MERGE (s)-[r:AP_DUNG_CHO]->(t)
SET r.method = row.method, r.confidence = row.confidence, r.evidence = row.evidence
RETURN count(r) AS so_ap_dung_cho;

// BƯỚC 8.4 — [:AP_DUNG_CHO] (57 edge)_phan2
UNWIND [
  {source: '27/2024/TT-NHNN', target: 'Tổ chức, cá nhân có liên quan đến phạm vi điều chỉnh quy định tại Điều 1 Thông tư này', method: 'claude_llm', confidence: 0.85, evidence: '3. Tổ chức, cá nhân có liên quan đến phạm vi điều chỉnh quy định tại Điều 1 Thông tư này.'},
  {source: '73/2016/NĐ-CP', target: 'Doanh nghiệp môi giới bảo hiểm', method: 'claude_llm', confidence: 0.85, evidence: 'Doanh nghiệp bảo hiểm phi nhân thọ, doanh nghiệp bảo hiểm nhân thọ, doanh nghiệp bảo hiểm sức khỏe (sau đây gọi là doanh nghiệp bảo hiểm), doanh nghiệp tái bảo '},
  {source: '62/2024/TT-NHNN', target: 'Tổ chức, cá nhân có liên quan đến việc tổ chức lại tổ chức tín dụng', method: 'claude_llm', confidence: 0.85, evidence: '2. Tổ chức, cá nhân có liên quan đến việc tổ chức lại tổ chức tín dụng.'},
  {source: '202/2012/TT-BTC', target: 'Tổ chức, cá nhân có liên quan đến việc đăng ký, quản lý và công khai danh sách kiểm toán viên hành nghề kiểm toán', method: 'claude_llm', confidence: 0.85, evidence: '3. Tổ chức, cá nhân có liên quan đến việc đăng ký, quản lý và công khai danh sách kiểm toán viên hành nghề kiểm toán.'},
  {source: '52/VBHN-NHNN', target: 'Tổ chức, cá nhân có liên quan đến hồ sơ, thủ tục cấp Giấy phép lần đầu của ngân hàng thương mại, chi nhánh ngân hàng nước ngoài và văn phòng đại diện nước ngoài', method: 'claude_llm', confidence: 0.85, evidence: '4. Các tổ chức, cá nhân có liên quan đến hồ sơ, thủ tục cấp Giấy phép lần đầu của ngân hàng thương mại, chi nhánh ngân hàng nước ngoài và văn phòng đại diện nướ'},
  {source: '56/2024/TT-NHNN', target: 'Tổ chức, cá nhân có liên quan đến hồ sơ, thủ tục cấp Giấy phép lần đầu của ngân hàng thương mại, chi nhánh ngân hàng nước ngoài và văn phòng đại diện nước ngoài', method: 'claude_llm', confidence: 0.85, evidence: '4. Các tổ chức, cá nhân có liên quan đến hồ sơ, thủ tục cấp Giấy phép lần đầu của ngân hàng thương mại, chi nhánh ngân hàng nước ngoài và văn phòng đại diện nướ'},
  {source: '105/2016/TT-BTC', target: 'Quỹ đầu tư chứng khoán', method: 'claude_llm', confidence: 0.85, evidence: 'Thông tư này áp dụng đối với tổ chức kinh doanh chứng khoán, quỹ đầu tư chứng khoán, công ty đầu tư chứng khoán, doanh nghiệp kinh doanh bảo hiểm và các cơ quan'},
  {source: '17/VBHN-BTC', target: 'Ngân hàng thương mại, chi nhánh ngân hàng nước ngoài tại Việt Nam thực hiện hoạt động lưu ký, bù trừ, thanh toán giao dịch chứng khoán, ngân hàng giám sát', method: 'claude_llm', confidence: 0.85, evidence: 'k) Ngân hàng thương mại, chi nhánh ngân hàng nước ngoài tại Việt Nam thực hiện hoạt động lưu ký, bù trừ, thanh toán giao dịch chứng khoán, ngân hàng giám sát;'},
  {source: '46/2023/NĐ-CP', target: 'Người thụ hưởng', method: 'claude_llm', confidence: 0.85, evidence: '3. Bên mua bảo hiểm, người được bảo hiểm, người thụ hưởng'},
  {source: '17/VBHN-BTC', target: 'Tổ chức khác hoạt động trên thị trường chứng khoán hoặc có liên quan đến hoạt động về chứng khoán và thị trường chứng khoán', method: 'claude_llm', confidence: 0.85, evidence: 'm) Các tổ chức khác hoạt động trên thị trường chứng khoán hoặc có liên quan đến hoạt động về chứng khoán và thị trường chứng khoán.'},
  {source: '46/2023/NĐ-CP', target: 'Tổ chức, cá nhân cung cấp dịch vụ phụ trợ bảo hiểm', method: 'claude_llm', confidence: 0.85, evidence: 'Doanh nghiệp bảo hiểm phi nhân thọ, doanh nghiệp bảo hiểm nhân thọ, doanh nghiệp bảo hiểm sức khỏe (sau đây gọi là doanh nghiệp bảo hiểm), doanh nghiệp tái bảo '},
  {source: '17/VBHN-BTC', target: 'Tổ chức, cá nhân Việt Nam và tổ chức, cá nhân nước ngoài', method: 'claude_llm', confidence: 0.85, evidence: 'Tổ chức, cá nhân Việt Nam và tổ chức, cá nhân nước ngoài (sau đây gọi chung là Tổ chức, cá nhân) thực hiện hành vi vi phạm hành chính trong lĩnh vực chứng khoán'},
  {source: '44/2011/TT-NHNN', target: 'Tổ chức, cá nhân có liên quan đến hệ thống kiểm soát nội bộ và kiểm toán nội bộ của tổ chức tín dụng, chi nhánh ngân hàng nước ngoài', method: 'claude_llm', confidence: 0.85, evidence: '3. Tổ chức, cá nhân có liên quan đến hệ thống kiểm soát nội bộ và kiểm toán nội bộ của tổ chức tín dụng, chi nhánh ngân hàng nước ngoài.'},
  {source: '62/2025/TT-NHNN', target: 'Tổ chức, cá nhân có liên quan đến hệ thống kiểm soát nội bộ của tổ chức tín dụng', method: 'claude_llm', confidence: 0.85, evidence: '3. Tổ chức, cá nhân có liên quan đến hệ thống kiểm soát nội bộ của tổ chức tín dụng.'},
  {source: '46/2023/NĐ-CP', target: 'Người được bảo hiểm', method: 'claude_llm', confidence: 0.85, evidence: '3. Bên mua bảo hiểm, người được bảo hiểm, người thụ hưởng'},
  {source: '01/2014/TT-NHNN', target: 'Ngân hàng Nhà nước Việt Nam', method: 'claude_llm', confidence: 0.85, evidence: '1. Ngân hàng Nhà nước Việt Nam (sau đây gọi tắt là Ngân hàng Nhà nước).'},
  {source: '01/2014/TT-NHNN', target: 'Khách hàng trong quan hệ giao dịch tiền mặt, tài sản quý, giấy tờ có giá với Ngân hàng Nhà nước, tổ chức tín dụng, chi nhánh ngân hàng nước ngoài', method: 'claude_llm', confidence: 0.85, evidence: '3. Khách hàng trong quan hệ giao dịch tiền mặt, tài sản quý, giấy tờ có giá với Ngân hàng Nhà nước, tổ chức tín dụng, chi nhánh ngân hàng nước ngoài.'},
  {source: '46/2023/NĐ-CP', target: 'Doanh nghiệp môi giới bảo hiểm', method: 'claude_llm', confidence: 0.85, evidence: 'Doanh nghiệp bảo hiểm phi nhân thọ, doanh nghiệp bảo hiểm nhân thọ, doanh nghiệp bảo hiểm sức khỏe (sau đây gọi là doanh nghiệp bảo hiểm), doanh nghiệp tái bảo '},
  {source: '46/2023/NĐ-CP', target: 'Doanh nghiệp bảo hiểm phi nhân thọ', method: 'claude_llm', confidence: 0.85, evidence: 'Doanh nghiệp bảo hiểm phi nhân thọ, doanh nghiệp bảo hiểm nhân thọ, doanh nghiệp bảo hiểm sức khỏe (sau đây gọi là doanh nghiệp bảo hiểm), doanh nghiệp tái bảo '},
  {source: '46/2023/NĐ-CP', target: 'Doanh nghiệp bảo hiểm sức khỏe', method: 'claude_llm', confidence: 0.85, evidence: 'Doanh nghiệp bảo hiểm phi nhân thọ, doanh nghiệp bảo hiểm nhân thọ, doanh nghiệp bảo hiểm sức khỏe (sau đây gọi là doanh nghiệp bảo hiểm), doanh nghiệp tái bảo '},
  {source: '46/2023/NĐ-CP', target: 'Doanh nghiệp tái bảo hiểm', method: 'claude_llm', confidence: 0.85, evidence: 'Doanh nghiệp bảo hiểm phi nhân thọ, doanh nghiệp bảo hiểm nhân thọ, doanh nghiệp bảo hiểm sức khỏe (sau đây gọi là doanh nghiệp bảo hiểm), doanh nghiệp tái bảo '},
  {source: '17/VBHN-BTC', target: 'Doanh nghiệp nhà nước, công ty trách nhiệm hữu hạn một thành viên do doanh nghiệp nhà nước nắm giữ 100% vốn điều lệ, đơn vị sự nghiệp công lập cổ phần hóa dưới hình thức chào bán chứng khoán ra công chúng', method: 'claude_llm', confidence: 0.85, evidence: 'b) Doanh nghiệp nhà nước, công ty trách nhiệm hữu hạn một thành viên do doanh nghiệp nhà nước nắm giữ 100% vốn điều lệ, đơn vị sự nghiệp công lập cổ phần hóa dư'},
  {source: '41/2016/TT-NHNN', target: 'Ngân hàng thương mại cổ phần', method: 'claude_llm', confidence: 0.85, evidence: 'a) Ngân hàng: Ngân hàng thương mại nhà nước, ngân hàng thương mại cổ phần, ngân hàng liên doanh, ngân hàng 100% vốn nước ngoài;'},
  {source: '41/2016/TT-NHNN', target: 'Ngân hàng liên doanh', method: 'claude_llm', confidence: 0.85, evidence: 'a) Ngân hàng: Ngân hàng thương mại nhà nước, ngân hàng thương mại cổ phần, ngân hàng liên doanh, ngân hàng 100% vốn nước ngoài;'},
  {source: '41/2016/TT-NHNN', target: 'Ngân hàng thương mại nhà nước', method: 'claude_llm', confidence: 0.85, evidence: 'a) Ngân hàng: Ngân hàng thương mại nhà nước, ngân hàng thương mại cổ phần, ngân hàng liên doanh, ngân hàng 100% vốn nước ngoài;'},
  {source: '41/2016/TT-NHNN', target: 'Ngân hàng 100% vốn nước ngoài', method: 'claude_llm', confidence: 0.85, evidence: 'a) Ngân hàng: Ngân hàng thương mại nhà nước, ngân hàng thương mại cổ phần, ngân hàng liên doanh, ngân hàng 100% vốn nước ngoài;'},
  {source: '32/2024/QH15', target: 'Tổ chức mà Nhà nước sở hữu 100% vốn điều lệ có chức năng mua, bán, xử lý nợ', method: 'claude_llm', confidence: 0.85, evidence: 'Tổ chức mà Nhà nước sở hữu 100% vốn điều lệ có chức năng mua, bán, xử lý nợ (sau đây gọi là tổ chức mua bán, xử lý nợ).'},
  {source: '105/2016/TT-BTC', target: 'Tổ chức kinh doanh chứng khoán', method: 'claude_llm', confidence: 0.85, evidence: 'Thông tư này áp dụng đối với tổ chức kinh doanh chứng khoán, quỹ đầu tư chứng khoán, công ty đầu tư chứng khoán, doanh nghiệp kinh doanh bảo hiểm và các cơ quan'},
  {source: '62/2024/TT-NHNN', target: 'Tổ chức tín dụng phi ngân hàng bao gồm công ty tài chính tổng hợp và công ty tài chính chuyên ngành', method: 'claude_llm', confidence: 0.85, evidence: 'b) Tổ chức tín dụng phi ngân hàng bao gồm công ty tài chính tổng hợp và công ty tài chính chuyên ngành.'},
  {source: '46/2023/NĐ-CP', target: 'Tổ chức tương hỗ cung cấp bảo hiểm vi mô', method: 'claude_llm', confidence: 0.85, evidence: 'Doanh nghiệp bảo hiểm phi nhân thọ, doanh nghiệp bảo hiểm nhân thọ, doanh nghiệp bảo hiểm sức khỏe (sau đây gọi là doanh nghiệp bảo hiểm), doanh nghiệp tái bảo '},
  {source: '73/2016/NĐ-CP', target: 'Tổ chức, cá nhân khác có liên quan', method: 'claude_llm', confidence: 0.85, evidence: 'd) Các tổ chức, cá nhân khác có liên quan.'},
  {source: '135/2015/NĐ-CP', target: 'Tổ chức, cá nhân khác có liên quan đến hoạt động đầu tư gián tiếp ra nước ngoài', method: 'claude_llm', confidence: 0.85, evidence: '3. Các tổ chức, cá nhân khác có liên quan đến hoạt động đầu tư gián tiếp ra nước ngoài.'},
  {source: '73/2016/NĐ-CP', target: 'Đại lý bảo hiểm', method: 'claude_llm', confidence: 0.85, evidence: 'Doanh nghiệp bảo hiểm phi nhân thọ, doanh nghiệp bảo hiểm nhân thọ, doanh nghiệp bảo hiểm sức khỏe (sau đây gọi là doanh nghiệp bảo hiểm), doanh nghiệp tái bảo '},
  {source: '57/2024/TT-NHNN', target: 'Tổ chức, cá nhân có liên quan đến việc cấp Giấy phép lần đầu của tổ chức tín dụng phi ngân hàng', method: 'claude_llm', confidence: 0.85, evidence: '3. Các tổ chức, cá nhân có liên quan đến việc cấp Giấy phép lần đầu của tổ chức tín dụng phi ngân hàng.'},
  {source: '29/2024/TT-NHNN', target: 'Tổ chức, cá nhân có liên quan đến quản trị, điều hành, tổ chức và hoạt động của quỹ tín dụng nhân dân', method: 'claude_llm', confidence: 0.85, evidence: '3. Tổ chức, cá nhân có liên quan đến quản trị, điều hành, tổ chức và hoạt động của quỹ tín dụng nhân dân.'},
  {source: '37/2014/TT-NHNN', target: 'Tổ chức, cá nhân khác có liên quan đến công việc thiết kế mẫu tiền, chế tạo bản in, khuôn đúc và in, đúc tiền', method: 'claude_llm', confidence: 0.85, evidence: '3. Tổ chức, cá nhân khác có liên quan đến công việc thiết kế mẫu tiền, chế tạo bản in, khuôn đúc và in, đúc tiền.'},
  {source: '32/2024/QH15', target: 'Văn phòng đại diện tại Việt Nam của tổ chức tín dụng nước ngoài, tổ chức nước ngoài khác có hoạt động ngân hàng', method: 'claude_llm', confidence: 0.85, evidence: 'Văn phòng đại diện tại Việt Nam của tổ chức tín dụng nước ngoài, tổ chức nước ngoài khác có hoạt động ngân hàng (sau đây gọi là văn phòng đại diện nước ngoài).'},
  {source: '52/VBHN-NHNN', target: 'Văn phòng đại diện tại Việt Nam của tổ chức tín dụng nước ngoài, tổ chức nước ngoài khác có hoạt động ngân hàng', method: 'claude_llm', confidence: 0.85, evidence: 'Văn phòng đại diện tại Việt Nam của tổ chức tín dụng nước ngoài, tổ chức nước ngoài khác có hoạt động ngân hàng (sau đây gọi là văn phòng đại diện nước ngoài).'},
  {source: '05/2019/NĐ-CP', target: 'Tổ chức, cá nhân khác có liên quan đến hoạt động kiểm toán nội bộ', method: 'claude_llm', confidence: 0.85, evidence: 'đ) Các tổ chức, cá nhân khác có liên quan đến hoạt động kiểm toán nội bộ.'},
  {source: '56/2024/TT-NHNN', target: 'Văn phòng đại diện tại Việt Nam của tổ chức tín dụng nước ngoài, tổ chức nước ngoài khác có hoạt động ngân hàng', method: 'claude_llm', confidence: 0.85, evidence: 'Văn phòng đại diện tại Việt Nam của tổ chức tín dụng nước ngoài, tổ chức nước ngoài khác có hoạt động ngân hàng (sau đây gọi là văn phòng đại diện nước ngoài).'},
  {source: '01/2025/TT-NHNN', target: 'Tổ chức, cá nhân có liên quan đến việc cấp Giấy phép lần đầu, cấp đổi Giấy phép của quỹ tín dụng nhân dân, cấp bản sao Giấy phép từ sổ gốc', method: 'claude_llm', confidence: 0.85, evidence: '2. Tổ chức, cá nhân có liên quan đến việc cấp Giấy phép lần đầu, cấp đổi Giấy phép của quỹ tín dụng nhân dân, cấp bản sao Giấy phép từ sổ gốc.'},
  {source: '46/2023/NĐ-CP', target: 'Chi nhánh doanh nghiệp bảo hiểm phi nhân thọ nước ngoài', method: 'claude_llm', confidence: 0.8, evidence: 'Chi nhánh doanh nghiệp bảo hiểm phi nhân thọ nước ngoài, chi nhánh doanh nghiệp tái bảo hiểm nước ngoài (sau đây gọi là chi nhánh nước ngoài tại Việt Nam); Văn '},
  {source: '46/2023/NĐ-CP', target: 'Chi nhánh doanh nghiệp tái bảo hiểm nước ngoài', method: 'claude_llm', confidence: 0.8, evidence: 'Chi nhánh doanh nghiệp bảo hiểm phi nhân thọ nước ngoài, chi nhánh doanh nghiệp tái bảo hiểm nước ngoài (sau đây gọi là chi nhánh nước ngoài tại Việt Nam); Văn '},
  {source: '67/2011/QH12', target: 'doanh nghiệp kiểm toán', method: 'claude_llm', confidence: 0.8, evidence: 'Luật này áp dụng đối với kiểm toán viên, kiểm toán viên hành nghề, doanh nghiệp kiểm toán, chi nhánh doanh nghiệp kiểm toán nước ngoài tại Việt Nam, đơn vị được'},
  {source: '67/2011/QH12', target: 'tổ chức, cá nhân khác có liên quan đến hoạt động kiểm toán độc lập', method: 'claude_llm', confidence: 0.8, evidence: 'Luật này áp dụng đối với kiểm toán viên, kiểm toán viên hành nghề, doanh nghiệp kiểm toán, chi nhánh doanh nghiệp kiểm toán nước ngoài tại Việt Nam, đơn vị được'},
  {source: '67/2011/QH12', target: 'tổ chức nghề nghiệp về kiểm toán', method: 'claude_llm', confidence: 0.8, evidence: 'Luật này áp dụng đối với kiểm toán viên, kiểm toán viên hành nghề, doanh nghiệp kiểm toán, chi nhánh doanh nghiệp kiểm toán nước ngoài tại Việt Nam, đơn vị được'},
  {source: '135/2015/NĐ-CP', target: 'Tổ chức kinh tế có vốn đầu tư nước ngoài (thuộc đối tượng quy định tại Khoản 1 Điều 23 Luật Đầu tư)', method: 'claude_llm', confidence: 0.8, evidence: '4. Tổ chức kinh tế có vốn đầu tư nước ngoài (thuộc đối tượng quy định tại Khoản 1 Điều 23 Luật Đầu tư) không được thực hiện đầu tư gián tiếp ra nước ngoài theo '},
  {source: '105/2016/TT-BTC', target: 'Cơ quan, tổ chức, cá nhân có liên quan đến hoạt động đầu tư gián tiếp ra nước ngoài', method: 'claude_llm', confidence: 0.8, evidence: 'Thông tư này áp dụng đối với tổ chức kinh doanh chứng khoán, quỹ đầu tư chứng khoán, công ty đầu tư chứng khoán, doanh nghiệp kinh doanh bảo hiểm và các cơ quan'},
  {source: '32/2024/QH15', target: 'Cơ quan, tổ chức, cá nhân có liên quan đến việc thành lập, tổ chức, hoạt động, can thiệp sớm, kiểm soát đặc biệt, tổ chức lại, giải thể, phá sản tổ chức tín dụng', method: 'claude_llm', confidence: 0.8, evidence: '5. Cơ quan, tổ chức, cá nhân có liên quan đến việc thành lập, tổ chức, hoạt động, can thiệp sớm, kiểm soát đặc biệt, tổ chức lại, giải thể, phá sản tổ chức tín '},
  {source: '08/2021/TT-BTC', target: 'Doanh nghiệp, cơ quan nhà nước, đơn vị sự nghiệp công lập quy định tại Điều 8, Điều 9, Điều 10 Nghị định số 05/2019/NĐ-CP', method: 'claude_llm', confidence: 0.8, evidence: 'Chuẩn mực kiểm toán nội bộ Việt Nam và các nguyên tắc đạo đức nghề nghiệp kiểm toán nội bộ áp dụng đối với các doanh nghiệp, cơ quan nhà nước, đơn vị sự nghiệp '},
  {source: '46/2023/NĐ-CP', target: 'Văn phòng đại diện của doanh nghiệp bảo hiểm nước ngoài, doanh nghiệp tái bảo hiểm nước ngoài, doanh nghiệp môi giới bảo hiểm nước ngoài, tập đoàn tài chính, bảo hiểm nước ngoài tại Việt Nam', method: 'claude_llm', confidence: 0.8, evidence: 'Văn phòng đại diện của doanh nghiệp bảo hiểm nước ngoài, doanh nghiệp tái bảo hiểm nước ngoài, doanh nghiệp môi giới bảo hiểm nước ngoài, tập đoàn tài chính, bả'},
  {source: '67/2011/QH12', target: 'đơn vị được kiểm toán', method: 'claude_llm', confidence: 0.8, evidence: 'Luật này áp dụng đối với kiểm toán viên, kiểm toán viên hành nghề, doanh nghiệp kiểm toán, chi nhánh doanh nghiệp kiểm toán nước ngoài tại Việt Nam, đơn vị được'},
  {source: '67/2011/QH12', target: 'chi nhánh doanh nghiệp kiểm toán nước ngoài tại Việt Nam', method: 'claude_llm', confidence: 0.8, evidence: 'Luật này áp dụng đối với kiểm toán viên, kiểm toán viên hành nghề, doanh nghiệp kiểm toán, chi nhánh doanh nghiệp kiểm toán nước ngoài tại Việt Nam, đơn vị được'},
  {source: '67/2011/QH12', target: 'kiểm toán viên', method: 'claude_llm', confidence: 0.8, evidence: 'Luật này áp dụng đối với kiểm toán viên, kiểm toán viên hành nghề, doanh nghiệp kiểm toán, chi nhánh doanh nghiệp kiểm toán nước ngoài tại Việt Nam, đơn vị được'},
  {source: '67/2011/QH12', target: 'kiểm toán viên hành nghề', method: 'claude_llm', confidence: 0.8, evidence: 'Luật này áp dụng đối với kiểm toán viên, kiểm toán viên hành nghề, doanh nghiệp kiểm toán, chi nhánh doanh nghiệp kiểm toán nước ngoài tại Việt Nam, đơn vị được'},
  {source: '08/2021/TT-BTC', target: 'Tổ chức cá nhân có liên quan trong hoạt động kiểm toán nội bộ của các đơn vị này', method: 'claude_llm', confidence: 0.75, evidence: 'Chuẩn mực kiểm toán nội bộ Việt Nam và các nguyên tắc đạo đức nghề nghiệp kiểm toán nội bộ áp dụng đối với các doanh nghiệp, cơ quan nhà nước, đơn vị sự nghiệp '},
  {source: '66/2020/TT-BTC', target: 'Doanh nghiệp không thuộc quy định tại khoản 1 Điều này', method: 'claude_llm', confidence: 0.6, evidence: 'Các doanh nghiệp không thuộc quy định tại khoản 1 Điều này được khuyến khích xây dựng Quy chế kiểm toán nội bộ trên cơ sở tham chiếu mẫu Quy chế kiểm toán nội b'}
] AS row
MATCH (s:Document {so_ky_hieu: row.source})
MATCH (t:DoiTuongApDung {canonical_name: row.target})
MERGE (s)-[r:AP_DUNG_CHO]->(t)
SET r.method = row.method, r.confidence = row.confidence, r.evidence = row.evidence
RETURN count(r) AS so_ap_dung_cho;