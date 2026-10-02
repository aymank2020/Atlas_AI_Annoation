# عقد المهايئ والترحيل المحلي

الإصدار 0.2.0 يضيف مهايئ exports محليًا؛ لا يرحّل workers أو جلسات المتصفح.
الواجهة والمكتبة وCLI تستعمل المسار نفسه إلى النواة المستخلصة.

## المدخلات العامة

`parse_segments(raw_json, label="snapshot")` يعيد قائمة المقاطع، أو يرفع
ValueError/خطأ JSON إذا تعذرت البنية، أو RecursionError لعمق يفوق decoder.
واجهة التقرير وCLI وHTTP تحول هذه الأخطاء إلى input_error2. يقبل الصيغتين المحفوظتين من CLI:

```json
[{"segment_index":1,"start_sec":0,"end_sec":4,"current_label":"synthetic"}]
```

```json
{"segments":[{"segment_index":1,"start_sec":"0","end_sec":"4","label":"synthetic"}]}
```

حقول wrapper الأخرى تظل metadata غير مستخدمة في قرار الاتساق؛ العدد الفعلي
يحسب من القائمة، ولا يصدق segment_count أو checksum مرسلين داخل الملف.
المعرف integer وليس boolean. المعرف غير الموجب يدخل الحارس ويمنع النجاح.
numeric timestamp strings محفوظة للتوافق؛ Boolean timestamp خطأ بنية،
والقيم الناقصة وغير المحدودة والفترات غير الصالحة أسباب منع داخل النواة.
label/current_label يمران إلى بصمة المقاطع، دون تدقيق جودة التسمية.

حد النص 256 KiB ببايتات UTF-8، وعدد المقاطع 1000 لكل ملف. يدعم UTF-8 BOM
وLF وCRLF. [fixture Windows](../tests/fixtures/windows-snapshot.json) يحفظ
BOM وصيغة wrapper والأزمنة النصية؛ [fixture Linux](../tests/fixtures/linux-snapshot.json)
قائمة UTF-8 بلا BOM. اختبار النقل ينشئ كذلك صيغة CRLF ويحافظ على بصمتها الخام.
لا تحويل إلى مخطط جديد أو تعديل ملفات قديمة عند القراءة.

## تقرير موحد

```python
from atlas_annotation import review_snapshot_json

report = review_snapshot_json(
    live_json=live_text,
    source_json=source_text,
    plan_json=optional_plan_text,
    tolerance_sec=0.25,
)
```

التقرير قابل لإخراج JSON صارم. schema_version=1، scope=snapshot_integrity،
submit_authorized=false، status=matched/blocked/input_error، وexit_code=0/1/2.
يحفظ reason/reasons وأسباب النواة وتحذيرات AI، وصفوفًا حسب segment_index.
معرف الصف string يحفظ المعرف الصحيح كاملًا دون تقريب أرقام JavaScript الكبيرة.
كل صف يحفظ occurrences في DOM والمصدر والخطة، وفروق الأزمنة المحدودة أو null،
وأسباب المنع/التحذير؛ التكرار لا يختفي خلف آخر occurrence.
القيم غير المحدودة تمثل كنص في الخلايا. العرض النصي الطويل يقصر بعد2000 حرف
مع إشارة واضحة؛ لا يستخدم النص المختصر لاتخاذ القرار أو حساب البصمة.
اتحاد الصفوف محدود3000 كحد أعلى مشتق من الملفات الثلاثة.

live_checksum/source_checksum هما SHA1 المختصر السابق لتوقيع المقاطع.
files.live/raw_sha256 وfiles.source/raw_sha256 يغطيان النص الخام ببايتاتUTF-8،
بما فيها BOM ونهايات الأسطر؛ الخطة لها بصمة أيضًا إذا قُدمت. لا تمثل البصمات
توقيعًا أو تفويضًا. قد تختلف بصمة المقاطع بسبب ترتيب القائمة أو label، بينما
قرار التوقيت مطابق؛ القرار لا يستبدل بمساواة checksum. إذا تعذر parsing تبقى
البصمة الخام متاحة ضمن الحد، وتكون بصمة المقاطع null. المدخل فوق الحد أو
غير القابل لترميز UTF-8 لا يحسب له digest وتظهر حالة input_error.

خطة AI لا تغير مرجع التوقيت. اختلاف المدة، offset فقط، الوقت غير المحدود
أو المكرر، والإشارة إلى مقطع غير موجود، تحذيرات فقط. خطأ بنية ملف الخطة
يبقى خطأ إدخال2 كما في CLI. لا سلطة للخطة لرفع سبب منع DOM/المصدر.

## HTTP والواجهة

POST `/api/review` يقبل application/json بهذه الحقول فقط:
live_json/source_json كـstrings خام، plan_json كـstring/null اختياري،
tolerance_sec اختياري. لا مسارات ملفات أو أسماء مطلوبة للخادم.
القرار المحلي، بما فيه input_error، يعاد HTTP200 مع exit_code المناسب.
خطأ envelope أو route/header/حجم جسم يعاد4xx؛ ليس قرار snapshot.
جسم الطلب محدود2MiB، وContent-Length واحد مطلوب؛ chunked غير مدعوم.
Host والـOrigin إن وُجد يجب أن يطابقا عنوان الخادم، وcross-site يرفض.
عملاء HTTP المحليون دون Origin ممكنون؛ هذه واجهة محلية دون حسابات.

الواجهة تقرأ ملفات اختارها المستخدم، ترسل النصوص إلى المهايئ، وتعرض النتيجة
بـtextContent. تغيير المدخل يبطل النتيجة والتنزيل القديم، والطلب المتأخر
لا يعيد إظهار نجاح سابق. التقرير في ذاكرة الصفحة حتى ينزله المستخدم؛ لا
localStorage أو كتابة تلقائية لملفات أو إرسال إلى خدمة خارجية.

## حدود الترحيل

API بناء ومقارنة اللقطات القديمة محفوظة، وread_segments في CLI باقية كمهايئ
ملف إلى parse_segments. نموذج JSON وexit0/1/2 وsubmit=false محفوظة؛ أضيفت
حقول تقرير وتحذيرات تفصيلية، وحدود موارد موثقة. لم تتغير snapshots.py.
المهايئ الحالي يقرأ exports فقط. نقل extractor حي أو إثبات بوابة الإرسال
من المستودعات القديمة يبقى عملًا مستقلًا؛ لا استدعاء مصادرها عند التشغيل.
