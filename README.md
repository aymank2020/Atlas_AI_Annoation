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

## واجهة المراجعة المحلية

```sh
python -m atlas_annotation.web --port 8081
# بعد تثبيت الحزمة:
atlas-snapshot-review --port 8081
```

افتح http://127.0.0.1:8081. اختر ملف DOM والمصدر، وخطة AI إن لزم، ثم
«مراجعة اللقطات». الجدول يعرض كل معرف والفروق والمقاطع المفقودة والتكرارات
وأسباب المنع وتحذيرات AI. «تنزيل تقرير المراجعة» يحفظ JSON بالحالة والأسباب
وبصمتي المقاطع وSHA256 للملفين الخامين وsubmit_authorized=false.
تغيير أي مدخل يلغي النتيجة القديمة. التقرير مؤقت حتى تنزله؛ الخادم لا يكتب
الملفات أو يحفظ بيانات المستخدم، ولا يتصل بحساب Atlas.

الربط المحلي 127.0.0.1 ثابت. `--port 0` يختار منفذًا متاحًا ويطبعه. الموارد
HTML/CSS/JS مضمنة في wheel؛ لا CDN أو ملفات خارجية. ملفات UTF-8/BOM حتى
256 KiB و1000 مقطع لكل ملف، وجسم HTTP حتى 2 MiB. النص الخام يصل إلى Python،
بما فيه NaN/Infinity، ثم يستعمل الحارس نفسه الذي يستعمله CLI. لا يستبدل
متصفح JavaScript هذه القيم بـnull. [عقد المهايئ](docs/ADAPTER_CONTRACT_AR.md)
و[بحث التصميم](docs/RESEARCH_LOCAL_REVIEW_AR.md) يوضحان الصيغ والحدود.

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
اجتاز المصدر السابق `a25ba355` بالفعل [GitHub Actions على Python 3.11–3.14](https://github.com/aymank2020/Atlas_AI_Annoation/actions/runs/37045518774).
التوسعة الحالية اجتازت 16 اختبارًا محليًا، مع 14 fixture تقارن التقرير كاملًا
بين المكتبة وCLI وHTTP، وحدود الملفات والمسارات وHost/Origin وBOM/CRLF.
اختبار wheel المثبتة يشغل console CLI والخادم وموارده من خارج checkout.
الواجهة اجتازت 14 مجموعة في Edge حقيقي تشمل رفع الملفات والتنزيل والكيبورد
وBOM وXSS كنص والهاتف 390px. CI للفرع الحالي ينتظر النشر.

لتكرار فحص wheel بعد تثبيتها: `python tests/wheel_consumer.py`.
إن كان التثبيت عبر pip --target، أضف `--target /path/to/install`.
فحص المتصفح اختياري، يحتاج Edge وPlaywright موجودًا دون تنزيل تبعيات:

```powershell
$env:PLAYWRIGHT_MODULE = 'C:\path\to\existing\node_modules\playwright'
$env:URL = 'http://127.0.0.1:8081/'
$env:OUTPUT_DIR = 'D:\path\to\atlas-test-evidence'
node tests/browser_consumer.cjs
```

## نطاق المرحلة الأولى والمتابعة

تم استخراج حارس snapshots واستكمال CLI والتغليف، ثم مهايئ exports موثق
لـWindows/Linux وواجهة المراجعة المحلية واختبارات HTTP والمتصفح. نقل
extractor حي أو قواعد الحلقة والتسمية والإرسال يبقى مرحلة مستقلة. لم تُنسخ
workers أو sessions أو حسابات أو إعدادات إنتاج من المستودعات القديمة.
