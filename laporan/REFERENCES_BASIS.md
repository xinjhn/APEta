# Basis Referensi Gambar dan Narasi

Dokumen ini dipakai untuk menjaga agar setiap gambar memiliki landasan teori,
standar, atau dokumentasi teknis yang jelas. Gambar yang dibuat dari sistem
sendiri tetap diberi sumber "diolah penulis"; referensi berikut menjelaskan
notasi atau konsep yang digunakan.

## Pemodelan dan Diagram

1. Larman, C. (2004). *Applying UML and Patterns: An Introduction to
   Object-Oriented Analysis and Design and Iterative Development* (3rd ed.).
   Prentice Hall.
   - Dipakai untuk pendekatan System Sequence Diagram (SSD), khususnya
     pemodelan aktor eksternal dan sistem sebagai black box.

2. Object Management Group. (2017). *Unified Modeling Language (UML) Version
   2.5.1*. https://www.omg.org/spec/UML/2.5.1
   - Dipakai untuk notasi sequence diagram, activity diagram, component
     diagram, dan deployment/component-style system view.

3. Object Management Group. (2014). *Business Process Model and Notation
   (BPMN) Version 2.0.2*. https://www.omg.org/spec/BPMN/2.0.2
   - Dipakai untuk proses penelitian, proses eksperimen, dan workflow
     stakeholder-level. BPMN tidak dipakai untuk detail internal API.

4. Chen, P. P. (1976). The Entity-Relationship Model: Toward a Unified View
   of Data. *ACM Transactions on Database Systems*, 1(1), 9-36.
   - Dipakai untuk diagram konseptual data/ERD dari korpus deteksi.

## API, Cache, dan Protokol

5. Fielding, R., Nottingham, M., & Reschke, J. (2022). *RFC 9110: HTTP
   Semantics*. https://www.rfc-editor.org/rfc/rfc9110.html
   - Dipakai untuk narasi request-response HTTP, metode GET, status response,
     resource, representation, client, server, dan intermediary.

6. Fielding, R., Nottingham, M., & Reschke, J. (2022). *RFC 9111: HTTP
   Caching*. https://www.rfc-editor.org/rfc/rfc9111.html
   - Dipakai untuk cache key, freshness, Cache-Control, ETag, validation,
     dan 304 Not Modified.

7. GraphQL Foundation. (2021). *GraphQL Specification, October 2021*.
   https://spec.graphql.org/October2021/
   - Dipakai untuk schema, query, resolver/execution, selection set, dan
     GraphQL response envelope.

8. Apollo GraphQL. *Automatic Persisted Queries*. 
   https://www.apollographql.com/docs/apollo-server/performance/apq/
   - Dipakai untuk alur APQ: hash-only request, PersistedQueryNotFound,
     registration request, dan reuse hash.

## Data, Computer Vision, dan Tooling

9. Zhu, P., Wen, L., Du, D., Bian, X., Fan, H., Hu, Q., & Ling, H. (2020).
   Detection and Tracking Meet Drones Challenge. arXiv:2001.06303.
   - Dipakai untuk konteks dataset VisDrone.

10. Ultralytics. *Object Detection* and *Multi-Object Tracking with
    Ultralytics YOLO*. https://docs.ultralytics.com/
    - Dipakai untuk konteks inference, tracking, dan penggunaan model YOLO.

11. Zhang, Y., Sun, P., Jiang, Y., Yu, D., Weng, F., Yuan, Z., Luo, P., Liu,
    W., & Wang, X. (2021). ByteTrack: Multi-Object Tracking by Associating
    Every Detection Box. arXiv:2110.06864.
    - Dipakai untuk dasar konsep tracking-by-detection dan ByteTrack.

12. Grafana Labs. *Grafana k6 Documentation*. https://grafana.com/docs/k6/
    - Dipakai untuk load/performance testing dan metrik k6.

13. Varnish Software. *Varnish Cache Documentation*. https://varnish-cache.org/docs/
    - Dipakai untuk reverse-proxy cache layer pada eksperimen.

14. SQLite. *SQLite Documentation*. https://www.sqlite.org/docs.html
    - Dipakai untuk basis penyimpanan relasional embedded yang digunakan oleh
      APE.

## Statistik

15. Mann, H. B., & Whitney, D. R. (1947). On a Test of Whether one of Two
    Random Variables is Stochastically Larger than the Other. *The Annals of
    Mathematical Statistics*, 18(1), 50-60.

16. Vargha, A., & Delaney, H. D. (2000). A Critique and Improvement of the
    CL Common Language Effect Size Statistics of McGraw and Wong. *Journal of
    Educational and Behavioral Statistics*, 25(2), 101-132.

17. Arcuri, A., & Briand, L. (2011). A Practical Guide for Using Statistical
    Tests to Assess Randomized Algorithms in Software Engineering. *ICSE 2011*.

