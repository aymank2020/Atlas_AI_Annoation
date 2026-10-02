# مراجعة وتطوير Atlas_AI_Annoation

التاريخ: 2 أكتوبر 2026. [المستودع](https://github.com/aymank2020/Atlas_AI_Annoation).
كان المستودع فارغًا. اكتملت نواة فحص snapshots أولًا، ثم شريحة الفكرة 3:
واجهة مراجعة محلية تستعمل النواة نفسها وتصدر تقريرًا قابلًا للتنزيل.

## المصدر وخط الأساس

اختير `atlas_hetzner_final_project` مصدرًا للنواة بعد اجتياز 353 اختبارًا
مع اختبار متجاوز، ثم 20 فحصًا مركّزًا. مصدر الاستخراج هو commit
`19c1f9c06e3b04b940f55bcc7b7d306d77fe0fb1`؛ الملف وبصمته وحدود الاستخراج
موثقة في [PROVENANCE.md](../PROVENANCE.md). لم تُنسخ workers أو جلسات أو
حسابات أو إعدادات إنتاج. لا diff في [snapshots.py](../atlas_annotation/snapshots.py)
مقابل خط الأساس `a25ba35507073745e38f66e308c7fca1804d86be`.

المرحلة الأولى أضافت CLI وتغليفًا دون تبعيات runtime وعشرة اختبارات محلية.
أصبح نجاح CI لهذه المرحلة متحققًا: [التشغيل 37045518774](https://github.com/aymank2020/Atlas_AI_Annoation/actions/runs/37045518774)
على Python 3.11 و3.12 و3.13 و3.14. هذا دليل للخط السابق فقط؛ CI للتوسعة
الحالية ينتظر نشر الفرع.

## الخطة المنفذة في الإصدار 0.2.0

1. **P1 — توحيد مسار المراجعة:** [review.py](../atlas_annotation/review.py)
   يقرأ نص JSON الخام، ويبني اللقطات ويستدعي الحارس الموجود. انتقل CLI إلى
   هذا المهايئ؛ بقيت أسماء API السابقة و`read_segments` وexit codes 0/1/2.
   أضيفت `parse_segments` و`review_snapshot_json` كواجهتين عامتين موثقتين.
2. **P1 — واجهة فعلية:** [web.py](../atlas_annotation/web.py) وموارد
   [ui](../atlas_annotation/ui/index.html) تقبل ملفي DOM والمصدر، وخطة AI
   اختيارية. الجدول يعرض المعرفات والفروق والمفقود والتكرار وأسباب المنع
   والتحذير؛ يحتفظ بكل occurrences بدل إخفاء التكرار خلف آخر قيمة.
3. **P1 — تقرير قابل للتنزيل:** يحفظ status وreason/reasons وexit code
   وبصمتي المقاطع وSHA256 لكل نص خام، مع `submit_authorized=false` دائمًا.
   NaN/Infinity لا تتحول إلى null قبل وصولها إلى Python. تغيير المدخل يلغي
   التقرير القديم والطلب المتأخر؛ الملف لا يكتب إلا عند تنزيله من المتصفح.
4. **P1 — حدود الموارد ومسارات HTTP:** الربط ثابت على 127.0.0.1، وموارد
   HTTP الثلاثة مضمنة في wheel. لا قراءة لمسار filesystem يرسله العميل.
   كل ملف حتى 256 KiB و1000 مقطع، والجسم حتى 2 MiB؛ Host/Origin وطلب
   cross-site والبنية غير الصحيحة تُفحص قبل المراجعة. النصوص تعرض بـtextContent.
5. **P2 — عقد ترحيل وfixtures:** [عقد المهايئ](ADAPTER_CONTRACT_AR.md)
   يحفظ الصيغتين array/segments-wrapper والأزمنة النصية المتوافقة مع CLI.
   fixtures لـUTF-8 وBOM، واختبار CRLF، وتوثيق ما يقرأ محليًا وما يبقى
   للترحيل الحي لاحقًا. لا يستورد التشغيل مصادر legacy أو يشغل خدماتها.
6. **P2 — تغليف واختبارات المستهلك:** console جديد `atlas-snapshot-review`،
   وpackage data للواجهة، و[اختبار wheel](../tests/wheel_consumer.py) في
   CI، و[اختبار Edge قابل للإعادة](../tests/browser_consumer.cjs) دون إضافة
   dependency إلى التطبيق.

## التحقق الفعلي

- `python -m unittest discover -s tests -v`: **16 اختبارًا ناجحًا** على
  Windows/Python 3.11.9. منها 14 fixture تقارن التقرير الكامل بين API
  المكتبة وCLI subprocess وPOST HTTP الحقيقي: صالح، NaN، Infinity، فراغ،
  تكرار، مقطع مفقود، مدة غير صالحة، drift، سماحية NaN، حد السماحية، JSON
  تالف، معرف غير صحيح، وتحذيرا AI للمدة والقيمة غير المحدودة.
- فحوص إضافية في [test_review_http.py](../tests/test_review_http.py): BOM
  وCRLF مع حفظ البصمة الخام، الحدود والحجم والعمق، Host/Origin والأنواع،
  Content-Length، whitelist الموارد، ومسارات filesystem المرفوضة.
- بناء wheel 0.2.0 بـ`pip wheel --no-build-isolation --no-deps --no-cache-dir`،
  ثم تثبيت `--target` جديد على D دون تنزيل dependencies: ناجح. SHA256:
  `51885fabbfd0f9284840d816b9dba52b529c0b68e2dbaa2ceeedcd36c1805c95`.
- `python tests/wheel_consumer.py --target <installation>`: **ناجح** من
  temporary cwd خارج checkout. شغّل executable CLI ثم executable الخادم
  من التثبيت، قرأ موارد wheel الثلاثة، وأرسل POST؛ التقرير يطابق CLI كاملًا
  مع exit 0 وتحذير AI وsubmit=false. اختبار CLI القديم ما زال يمر.
- `node tests/browser_consumer.cjs` عبر Playwright موجود وEdge فعلي:
  **14 مجموعة ناجحة**. اختيار ملفات حقيقي لعشر حالات، رفع BOM ببصمته
  الأصلية، تنزيل وقراءة تقارير صالح/NaN/JSON تالف عبر لوحة المفاتيح، عرض
  label يشبه HTML كنص، هاتف 390px وdesktop 1280px دون تجاوز عرض الصفحة،
  إبطال النتيجة عند التعديل، ورفض الملف الكبير برسالة ظاهرة. لا أخطاء صفحة
  أو dialogs أو طلبات خارج أصل الخادم المحلي. أُغلق المتصفح بعد الفحص.
- `node --check atlas_annotation/ui/app.js` ناجح. مراجعة diff أثبتت بقاء
  core الأصلي؛ `git diff --check` ناجح. الملفات الجديدة ومسارات الاستدعاء
  والموارد وentrypoints راجعت بعد الاختبارات.

الأدلة المحلية المحفوظة خارج Git موجودة في
`E:\1dollar\github-public-review\evidence\atlas-review\`:
`atlas-review-browser-result.json` يحفظ مجموعات الفحص وبصمات ملفات المصدر
قبل commit، و`atlas-review-wheel-receipt.json` يحفظ console paths وبصمات
الموارد والقرار، ومعهما التقارير الثلاثة المنزلة. لا يعتمد الدليل على W/tmp.
يتاح تكرار الفحص من سكربتي المستهلك الموجودين في المستودع. نتيجة Edge
الحالية لعامل التنفيذ؛ مراجعة root المستقلة والفرع الجديد لم تُعلن ناجحة بعد.

## فحص التكامل والأثر

قرئت وطُبقت مهارة Integration & Impact Review بعد مراجعة الكود والاختبارات.

مواضع الربط المراجعة: `review.py:34` للـparser و`review.py:167` للتقرير
المشترك، `web.py:86` لمسار POST و`web.py:129` للربط المحلي، و`ui/app.js:116`
للرفع و`ui/app.js:162` للتنزيل. جدول المستهلكين أدناه يربط هذه المواضع بنتائج
تشغيل فعلية، لا بمجرد وجود functions.

| نقطة الدخول | المستهلك الحقيقي والمسار | النتيجة المرصودة |
|---|---|---|
| `python -m atlas_annotation` أو `atlas-annotation` | `__main__`/console → `cli.main` → قراءة خام → `review_snapshot_json` → `build_segment_snapshot` و`compare_segment_snapshots` | JSON وexit 0/1/2؛ الحالات الأربع عشرة تعطي التقرير نفسه عبر library وHTTP |
| `atlas-snapshot-review` أو `python -m atlas_annotation.web` | console/module → `web.main` → خادم loopback → resources من package data | URL محلي، HTML/JS/CSS من wheel المثبتة خارج checkout |
| اختيار الملفين ثم «مراجعة اللقطات» | File API → نصوص خام → POST `/api/review` → المهايئ والنواة → DOM textContent | صفوف وقرار وتحذيرات ظاهرة؛ تقرير التنزيل يطابق HTTP ولا يمنح تفويض إرسال |
| API `review_snapshot_json` | المستهلك المكتبي/HTTP/CLI نفسه؛ لا validator آخر في JavaScript | نتيجة strict JSON حتى عند NaN/Infinity، مع أسباب وبصمات الخام |

إزالة الربط إلى المهايئ أو حذف موارد wheel يجعل checks المستهلك الفعلي
تفشل؛ لا mocks للمسار الداخلي. `read_segments` بقي للتوافق بدل ترك caller
قديمًا ينفذ parsing مستقلًا. API الحارس القديم محفوظة؛ أضيفت حقول تقرير
وحدود موارد موثقة وتحذيرات AI تفصيلية. زمن AI advisory؛ لا يرفع سبب منع
DOM/المصدر. لا listeners أو routes قديمة بديلة، ولا dependencies runtime
أضيفت. سكربتا المتصفح وwheel أدوات تحقق وليسا جزءًا من مسار مستخدم التطبيق.

## البحث والفجوات المتبقية

يوضح [بحث التصميم ومصادره الأولية](RESEARCH_LOCAL_REVIEW_AR.md) قرارات
JSON وmath.isfinite وhttp.server وpackage resources وTextDecoder/BOM.
المراجع الأساسية: [Python JSON](https://docs.python.org/3.11/library/json.html)،
[math.isfinite](https://docs.python.org/3/library/math.html#math.isfinite)،
[http.server](https://docs.python.org/3/library/http.server.html)،
[importlib.resources](https://docs.python.org/3/library/importlib.resources.html)،
[MDN TextDecoder](https://developer.mozilla.org/en-US/docs/Web/API/TextDecoder/ignoreBOM).

1. CI الجديد على Python 3.11–3.14/Linux ومراجعة root المستقلة ينتظران النشر
   والتحقق؛ لا تخلط نجاح CI السابق مع هذه التوسعة.
2. نقل extractor حي وإعادة الاستخراج من متصفح Atlas وربط قواعد الحلقة أو
   جودة labels لم يُنفذ. لا اختبارات لحساب حقيقي أو جلسة إنتاج.
3. بوابة إرسال خارجية أو عزل محادثات Gemini لم يُرحّلا. التقرير محلي
   للاتساق؛ `submit_authorized=false` لا يتغير بالنجاح.
4. الخادم المحلي stdlib أحادي الطلبات، دون authentication أو تخزين دائم؛
   ليس خدمة عامة. دعم الملفات الأكبر أو chunked أو مزامنة المستخدمين خارج
   هذه الشريحة؛ الحد والرفض الحاليان جزء من العقد الموثق.

اكتملت شريحة الواجهة المحلية وعقد exports المقروءة؛ يبقى توحيد التطبيق
الحي والنشر تشغيليًا مراحل مستقلة.
