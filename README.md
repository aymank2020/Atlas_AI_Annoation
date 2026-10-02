# Atlas Annotation Core

نواة محلية لفحص المقاطع المستخرجة من Atlas، مستخلصة من مصدر مختبر في
`atlas_hetzner_final_project`. هذه المرحلة توفر فحص سلامة وتزامن لقطات JSON؛
توجد خطة التوحيد وحدود المصدر في [PROVENANCE.md](PROVENANCE.md).

## التشغيل

يلزم Python 3.11 أو أحدث. يعمل الأمر من جذر المستودع دون تبعيات خارجية:

```sh
python -m atlas_annotation --live examples/live.json --source examples/source.json --plan examples/ai-plan.json
```

التثبيت الاختياري يضيف الأمر `atlas-annotation`:

```sh
python -m pip install .
atlas-annotation --live examples/live.json --source examples/source.json
```

كل ملف JSON إما قائمة مقاطع، أو كائن يحتوي `segments` كقائمة. حقول المقطع:

```json
{"segment_index": 1, "start_sec": 0.0, "end_sec": 4.0, "current_label": "pick up cup"}
```

المعرف عدد صحيح موجب، والمقاطع غير فارغة ولا تكرر المعرف. زمن البداية غير
سالب والنهاية أكبر من البداية؛ NaN وInfinity والمدد غير الصالحة تمنع النجاح
حتى إذا تطابقت اللقطتان. سماحية اختلاف الوقت افتراضيًا0.25 ثانية، قابلة
للضبط بـ`--tolerance-sec` مع قيمة محدودة وغير سالبة.

أزمنة `--plan` اختيارية للمقارنة التحذيرية: المصدر ولقطة DOM هما مرجع الوقت.
الفحص لا يدقق جودة التسمية أو كل قواعد الحلقة. JSON الناتج يصرح
`scope: snapshot_integrity` و`submit_authorized: false`؛ النجاح يثبت الاتساق
المحلي فقط، ولا يرسل أي إجراء إلى Atlas أو Gemini.

| Exit code | النتيجة |
|---|---|
| 0 | اللقطتان سليمتان ومتسقتان ضمن السماحية |
| 1 | سبب يمنع الاتساق؛ يحتاج استخراجًا/تصحيحًا |
| 2 | خطأ قراءة أو بنية JSON أو إعداد غير صالح |

## التحقق

```sh
python -m unittest discover -s tests -v
```

الاختبارات تمر عبر `python -m atlas_annotation` كعملية مستقلة، وتغطي
المدخل الصالح، NaN/Infinity/None، الفراغ والتكرار، فترات غير صالحة، انحراف
DOM عن المصدر، كون AI مجرد تحذير، وأخطاء الملفات/JSON/السماحية.
يوجد workflow يكررها على Python3.11–3.14؛ نجاح GitHub Actions يبقى غير
متحقق حتى النشر وتشغيل workflow.

## نطاق المرحلة الأولى والمتابعة

تم استخراج حارس snapshots واستكمال CLI والأمثلة والاختبارات والتغليف.
تبقى مهايئات Windows/Linux وواجهة مراجعة المقاطع واختبارات المتصفح في مراحل
لاحقة، بعد توثيق عقودها والبيئة المطلوبة. لم تُنسخ workers أو sessions أو
حسابات أو إعدادات إنتاج من المستودعات القديمة.
