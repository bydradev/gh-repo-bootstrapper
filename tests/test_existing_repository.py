"""Tests for --check and --adopt against existing local repositories."""

import os
import contextlib
import base64
import json
import zlib
import io
import subprocess
import sys
import shutil
import tempfile
import threading
import unittest
import unittest.mock
from pathlib import Path

import bootstrap
import validate_templates

# Exact v0.5.5 nextjs/Swift renders (sample, My App, iphone, XcodeGen) and
# historical docs from all release tags through v0.6.0. Captured from git show;
# compressed here because tests must also run without tags in a shallow clone.
_LEGACY_FIXTURES = json.loads(zlib.decompress(base64.b85decode(
    (
        'c-rlK|B~F+b>^!ebgeZ*clVGKCEG(;wG>6kj3siGl&oxJQUazMJp&O9v;p)C+b&n-uYG{6eTIFoJjtH#JLg_p^b92@m8xW;lS)~`'
        '?#9Laaeklgocou1#bwzH{k_xdFZY`A-S7kcy!Xl9&F9%?&%b=}@>D;Z^JnvJSC@S@pMQGZoHxJ7zPYOUO#c7nt8cR5s?1)>Zx=uG'
        '*}mOnZ=3c8zv6GM%dW55Cc7&7?4m1+w^ehQEw75^Qil7NfBrw&)3X=-EL*nCwY)}tDgP*%Rkp6`GV6zKw;Xm|nQe-FR@8O2s@ChW'
        '%hp}H!MnO_=!&Yrn5$wa7TN2vSaCvKS(n#EGh~;$YE@=cljTjjD!<>fE3D)Mi#u6Wz5GwR>`(ISs4M%nzAjff_<+e{5+C&P(ym+%'
        'ZMT1daW-w!cICG1`JNmD<=M7azLkyQJezjNF3Rk>>Z=P`gbjx&ZQHDC+u>NgUdtHSO;-(=d(rG=2Ug`G`+X@BSe09OVS(MiVAZnh'
        '7jZ)`>UQ}STaSl_vf*xZ<-Ay}<k5@0&Pc|%&bhyG0M%MHZ+Pzp^kpYMI;pFR6FKU#D~8ez9qaGqSaWRbroF~ot3g*(@GP>nsrPvO'
        'QqFcLbx(H9vfXSjyOkaFlgvJ`5pJsCO3&}6?cQc@%W|ua4qaJh%epKYu9(#L{N?9AO^e&E{Xq^X+x0eyr`v7zy4?+BhhOopKC7#1'
        'rG;X<l{0U<EbqJJ3I8?Y!Qs)f0>r5gXGi%K|2)Z$7xE^V;Z1wqbo{Q*3OPh2Ntu@rL07D*%T2HA8@~W;&e!Fzypr|LvbvC^52W++'
        'W>XFYz9%E_#8z$d!H{jLcbLp(k-b<eHInEm(4o*|zbw}4wqA`3=B#a{oh-5+gcoLbsxFqL4$;dN2~~~MWFKTQZlB4MJ(wlZ^>oK`'
        'q3-T2mMsr#cb&|pJUwp`dh1FMrOc-kg4z#Qt&sX~Qwo`4Ewij|LG1d?xSn~xEtl20TFQ3p`azFLW|LjX{$)d(^}Fs`K3nL4e<w6U'
        'LTbj1;Wxj?K9@Jw?RJA*2WhQql|`Q^!;u;(frJ%i*rY9pCUB?DM#N4r?0RD?lPCG>=TATX`guN+!w;fGB*zYKBB!d@!cRq(t*gsj'
        'rwoiwpS_5a$z&e<l^mbEx)cf!A`;2<MO))*h=PqwbuMgP)LH)Y%jYk@d9&E8avmw<A%rA%;t#?$QI@V{GQBWd+t_mcv@3gXpzNbC'
        'pU9T)uH+al%B$kK63&~EDrMGklovI&zG{SU)<P?@=@Mq(6D+#u%klZ};#s!a%1Grz>YmF`{UG1nu|=Ee(zXV}V%2ic!g{iXO6T4e'
        '8#^jJ@$V`SjDEFjx3YJ;;i~PbKdZo_$PpnXT(R7BWH?(r7a}re2bnZfHGYco3tJ=W-BgWiGfuoz9R*sI16f{S>pIyUVSruLlqz_I'
        'vqUySRSB!fwr=Z^43&M}QhfA7yUjL2wIUTSM25?}WYHP7c2lk@yk-NbI<(FBLd=P8Tx3tjNy*$-6*p?t%H~k5bZxPM%(o5TKAu9N'
        'hMx#IZABJd^R+wBYJru?lrH65MYGiH9tSdm#Jm=64+qIp7EUfZynD0LBU>0>z3OCoLVhDnujHsN`A;4ZXlwi^TNc~mqN-*3rAo=-'
        'x~S>``VbHIy9?QJITCplHNZ`~6Ipg4>StZa8mM8aMy6ZJ|Hy%s@5<#)X^66-sBQ5xO5M6H>#E;y4LEXHhlrA*5$UCiwW-M|wz~$3'
        'Qf4p|{o7ttu1pBF#s>BUn6tXP8fqxyot$paU~=4Q2FN!iTeEhZQSCvX?3$(&J>3@~Kh{Mv7os*PTgpyX8+=Y#D#W!BlLb<%-wG$I'
        'jQ~oMEf(QPdj}H+bwMIwk)XA<TM1d{nxR^%<*tU@T~@uCO(3$%z_LQ5Re6IchNZ8#)24OSq%hhBm0B92-LRJA=dy&Yu%^)HuF+r0'
        'hssAna3k%8_m->hTKS!POG1>j%QwpT*K%qr4qaSg3x?ZzO}SGx8pozm?hDzQaK;(WOdgYo!qgID2F4BTlo^D87)EU!7u$<jCiK^;'
        'nE~5EUT_0a?RVR4+sW^qWUUB=?xvDwdkBVRsiG{%Rnb^rRXw}*Mh*_FN(PaWGwE$y@*<(wwVdzOyxf<)ZAzksQt}V)0h26255kh5'
        'I+ZP@%HCqNCynSxLh~Z1+ioLoZzgPV>!lz770kU*%V>K?+O(fh?TXQA1FK*y5);POAEpp&aEy)Z!HEbZV9q$XQZ*rV-Sm!}REfp5'
        'V$H&Ojq(73sDw>lz}#<TZXLy8-_oqt=Y)D@*$u6MZC8j26x}$R%uj!}E=0KQ<J6KFnc%`Ixb`!ZezrNbB${oBI=Q7pXQN*+Qtgyx'
        'Rlb=$Q<z6HJpwhHgWz2S@+D)Aa?-d3)7D3OH9+HR`zs2~<ospnMKAVXuZ!35Ght2HIUEs2lHZt#5ch^I2zCY<v~8C4u8%fGLL>G*'
        'Z2vWesoVA~sdCwNkc<spT=o49i|Irp$iIVR3gkT9tC{FR`Hj53g~ckW?N2+J5^6k%ak>+Ga*uCCj$9YZJ?AGXsuz)%id-H4o%~qe'
        'CVV94cDId2hKKr-UEcHubQ1T1@<nVNp>Gj>SgWXKQjW679lQpiB%X^5vEJ30ETzWeAx!&IvG)cg@{#v%k>~bGO)Lrtk+D^Omq^f6'
        '*sqHCu@KKiSID7ryLO_?jC?VSsENA3AcwLfS}t}jGGHT12_g$Wq%m*$QB0UY4=XWfw!8jHiG>=(c0*K*D6Gr=P6eW5I?)6Z6P&#8'
        '9y|86I_k<GYL?;D;`?l8bjkRJCrmRV>=kD#ewF(C>WoY$Z7fHJU)I<qqB@FSnI&lnD)1*|usBOm*4qpd`!TvNI?9q}lbmui$f9xH'
        'tMsDC#0Ck`_oP~(s-;L<Q!&MAMN-bf#FqPsftMN!=S`rp3~r#gcEX$mekD3)X;xd{NBLT<6!9CNFqI-Z9PLJ#Nrc2A`&J!;WCmiA'
        'RckOeAHc~`_Q^uTqrOzxJBCtVzI9K;@KOqu&0Eb$fJJ<CA#N|!KIl|D16h##p@te5Dlmy?$qr_FM{`R?gu@*j5!%8l^{no+hUpcT'
        'bl4_NvJq!Ez31Wgh=7Udc&Xc#+QRtdw>>p|L-%hgpj5&3C2YZ|4Na@Xf@$-<Y+x8(%SsqENardvBHP;_jx;szjAnu{+KUgj1TkBH'
        'NY+zz^d96;^}YKEciPMK=%zky>WC`?n>Lek5VI9hk8e}Q0W`toR72z~TGimG9uiGWl<eE!JPB!w^(W)?Zz~w-h&d%Az%|k6kywW_'
        'p#^x-8fogMUUPKQO3Y5^xhtV)s9a=LI!pB;#2^xB)6q*t2x26Lvb$zTE}l2|A9F9J&KmSa2U1DoS~?rN#x@lWiJpfD3lV&s_;)H%'
        '+g1#nFRS7AyNg-&^|P~C_UwhYwc<3dQf(GzcgyigKM+n=C$(r)I;3tS7D>0SRCieSA7LBY@B=SgXytEo!vlZ37Kd1luhQ))VSkD6'
        'P{m<U+>vwOUkEAehIYMvqJlvTdm|D0pNXgh^?};rJ`e4VRH32+ZuNzDh~+v9)~yN#8v1-iwl2$BZ2Nb`Qq8Dy*cpRN3;GKtu02WH'
        'GR&O;E%E~Y8I~sWUR~le)GSW<P|gElDHBTGZe=(G{LBCr`PrDd5*8>6#CFQ%Tbv6+H2qanW>?rEJ%6=|WvA+*+Nd2b`hePB{-p7U'
        'U6+{_VEWV=loJ#k+=Za*TK2cz^RWJCL1Sb8BA)0}ddzOwmbB%@cgmifV!U~F|Nc`1xjD(=0wJFpIB`Wh)fobyWW7XRV6(uC1?hIx'
        'F7DqyZ!(Se%63sbU$l(1n#k{Q*1M(xW61$D3`mHvfPFr{H*m9fO2WqsM`JvV$;naOo9T}*mywapS(H6GzsG@WK5~q*#|4ijP{yX*'
        '&?U$)Z+;@aD;>S|0+Pdo@pD**HN@n|pz<#{f=l@R>q3kVYz79BJzw(VD-a2HRvql9`eCYy8NDpkV6_-lQ*7XphiroUZPRL?3B{aO'
        '3dAYYwQQTr4@0zTd&wcA;+sN$Wa1rjEB}V4I8pp#aYzdE<Pot!<Q$4CNRincG4BIgUUvsFK5oQBEeWv*rNHhI{;Hw7W3WVaOyn}%'
        'Jqs6w1<~Re#t6efG6(b{rx#8=#CvV}wBcJ-%{7T27$D2RIHMZOSSpRA7%2&MCwN_%K4q)|Bbk$Bf*NXiZ@c-&L#tp6(%!#+DmL1t'
        'VklOrO4Z$xiHIc8)RQ<cGmw6NRcskkPBhE=#qT0U04<=dmS?}0L*HPwt5SoS)cagl6}bu#mQ6WmW<=C+SCz19u(4}(Vi+bX$8bEh'
        'Fx?)}F`WsXTGfy^8ubd>Dk}w*nCzFulE@a>7gY_r19DGSX|b;Bw%)<Z$EmMrNs6kY`vbO@bGX`Xp>TUdFkodM&;e0G@?s9<rWr~9'
        '26C7*Db9j?Th?oaLqHMdP1w*N-OJJTsoTpm=+5Z)EU1GkhH0vHWjwFGzG|`PS-^`|ic&E<N*P99z{aYVpMsL)2Upc4cJ!j?NM9jI'
        'vl3>yfSvu+I5wmmg;84dJ~yz!;D?J!5|uLbJulkTewK~-z*{`bj0ZS=E|x0^N5mzJ*z-mX1(~2ea2aK~asU>kMtiv;6G0PVw=YU1'
        '5-~`&Wh?HLkX$R<qY}F>gW(?HOTsF`dNPE?sfw^-%%j9SjMSO+GBqo!qzb#m8)<rFSy@u#(DpSWDvU4IBPm0ZW1PL51L@5YO1C^p'
        '`ySd6E21X75jjEvVM<92gXmYP0cjo*xIJ=gky@t~Fam*$rX9vAZUq!DuLd@+Sih?h$0W~hg)3)cOuWc6ATeWvK&=cjT4hIrsS^@c'
        'XRl$eYHk&x!sLUxw&hm1_G=_D66^o{7N^ox%!RDdMao$Ti@t;A>OuKorCfB|w3~L<Yrf=(%wdTLlL#V2(`0kO_Amy`C5;b*fRX@j'
        '(WE<Q$(JAqEYh;d!ibCrhZk{w#5{o|ECYtDlVuIShvFFTEN{Y$q6n!ioS+!Q?Ta<ybF|VapT<z)=uO9`iXdk0P7jesr%r~9t@$BX'
        'PjMR1rpgrXAgj1J!+w#yq{VTu--^L`xc-?@i3r559aP0x%5gliR)$ok(ySNR=4CktUE!xpv#mtKRGOoL2C=ujZ(4tz<hMTK6yTrh'
        'R86eKl#gs;jswVr3X8X;#l(zXC>X*bj`DT&?&M$o`Typ#EME&Jguj>a){_4?jyxdGoxRquE~u(}w=B2nQTNag6YED7rwId24dL)g'
        'P7iKU6DEggS_}}T=aVE4FTB72q%7*PO(HH~;$b76ar7Q(7v`h?@mWOX$h+;^e>%DvhHZa(a&mKXvsfm-(8=|Sw!1tAHelFq%Oeuv'
        '@hL)|z-Y)Gej^|Er@BAfr|MnYBK!eN4*uIwLbe^!?m41v_z=-y{P$v4)hj+$>2GDR82k-$#O+pR^d!7CgSzgPAasVPN+lF1d!mSH'
        'NE%hF+zc^OU&v<9m0tSnmyl5FwgvD*EK3MrqXJWbV<<zxFw7q_Lsda0)7q3Fg(xd{;Gz=9uoYD`T)6yMJAcZzm8<z@`_o+KMKlM6'
        '-DNe{+khLP##Q2>?tu$@I7IddA_$*mN1rf3GKWv_>2dbSAfL{OW2*On4nY`xnp=)VhSA6JAnEaQAwfLNg{zY*n<ZMbps;1gys4IN'
        '<8NqC=jnSn9OK{Bu%j`sm(P*QvG4-lWf`C4Ko2Q+#cC1i;-6$OBG|3wfO1fOV<YJEaJnj2#h*uvwGVkPdYT#qp%%C*<OpCgivc$1'
        'v>E@#2n?c;yNu6;yVNP!)n#;RpULar89m(EeSUds^KIY%J0w6+3IA+9&26x{04d-x8xoTaHdDD8CB&&_JBL2l^)TPxPeAY%)dGty'
        '*nsfoH4MUMU%k+`-8Dvb@XK4PdGzS<$B!TW`q6KGby-3J&zE&I?^<!o|2vd(zp&*lgnF-b7wK|e$p$2Az4hww{g3V-fpbL_$Nc*2'
        'y~BNd_WqGJ+eLqcK@3+z(9f;?1P3NesRAIxOzT?&DjSdzZhTaug&1LCSFOr^*;QMMW4s6uu4wE$eIXu5(J|46qX?ioXh6o=`vXgD'
        'hPjnA;I4LJH_TyO7K%7%35_c>xGSeMw41;sBIuH-AQ6WI{1CFjRG;GXib4P@WJmdYKF^QI5_z5jCAOmRA|Hz!J?ro|Qu2Yt6A>tH'
        'yi-Ii?sF{DN@vNM`s}Fx)2<MUn08h6tL(M8NoV}eu|D&Q><z-4A|WO_Ld!RPbN1TIuVg^AcxA@Du6H^*DT^pKhDITW<r(hlKFWk|'
        's-X@<4ZVJc4vks~5|F;DdTkwY{viiJF$Jcq3vprPk&Wza^=F#IAUzrFVh8j}M5$y)<>GRoK%k6z^)xf_9#dRY?DO4Lehh=1d6k;('
        'x7iM<9k!&o3%`7SoMTKCN(FMoh0SPhGqp(^6S4@)#%3qxG&0|C##Ri}$g*W-rN$fvY!-bu8YuLbWHvQ40fL#;Wy9zx;0KMmQ54pe'
        'Qy(-ECY;46NpzoOzq^XLHd!t0$zHhB0G?)Z>8mdQwJ|SK2>~P7`OFe9NEmiMV*Nr!=3=+mTF}=7>}TTm1`;q+1RL9z##$G_|KTLy'
        '!q}k?bj!pkzRy+NzjIlqib5%nl<#DcsXe2zW^N0Z*JX1lr(DCQDh3TD)w@lTJy3=$;PcBg#3U09_f}qhq;$ifqtSLO<RPBZ+c^h{'
        '5`jmk<1~N-0KY+7yJ#$<g~ep|;~pe}Mdt)OmWVW=#HfQnO-KX6w{NI*OWk;VB1BRSIFl@E@SO423~Ti<HnW^^UyK_JVrL*o%G{#y'
        '<EC06s5WS5ztKQThRCWV<in}JD+9I5k(+<0PKu)Xl(LMsKo8S->yX7NCBQIE{JQ7*`;x2a)n+Ve`Sb$Govy3WU7|E%;8EuCgwcWf'
        'Z*)k0)!$c!5SL7xhIxLH-_M0h>za8mhA4<W7Li@5Y8Y7*fyzdA)@WRGkeSC2m160Z!7^6Oq<lXIsfY!!y%OI^RReajP>esEG@5J_'
        'SeKAK_O#-&^%JChbEPv;Hdq|N>G>0~Kv~!GKkZs5sQg^?22Ej+nj)nkBN5+?iE(Hri%*VPKw%NH5MLCISia@kl1Wi`e$srJ&F4S#'
        '$Svcv<?lab3;dZY#4RRMv$*QsD8@EzdK{yb$MG(OgBjqpm#T`J&y_54s#?A+guf@d!4w{ydJ0GA=HjBgE|0VOCgkqlL1gAh07j~`'
        'NWgf{uoB7GqDP9+WQHNs39N!7EaEW1Wk8sQw8Oy90jrYUMNJG!&P>Z_;8F;BZ@2~#eusirPZex%U*3EFw*B>f3s{l$CR%zW<;`~3'
        '2WAP>ud1vU%~sxF3t@HUu&ox^cfk%&$*!^+10Kkrj7bg?x&-gsB}rBCYZV0N+@JD<^ISDjN)bwjc8>EoK$}B3HyM+VMD~f=C-`8o'
        'S$%2)QfM;{oge%l7wfJzS#<XLgWhx&u_$ppy%`ZSkeKD;qSe<5lOD~$Ec;2H;!C;?*@uhYWM9-+)6ws%%d6vmqkEC8QY?{Zd?e01'
        'JaY}BS;QhS1923=DOW8U>FdXxtcjT{UL>~)x<NF89(Lef6Hu1ZIS6SA#aUEGc_7*MMfM6m)woG^)Dp0xmY#gF>qG<;byf7oV@$=O'
        'COE(lB8j$<%B544tBp$F$Z>P44e9fkR#Sv8S$MuxPL}@-5&BR|qSjd(lm}CU%yf-`boexC3TaL%y8=!khJE^BUzd}BP#OrzZij%l'
        'x@DDHYHE$WMpR7RDAT8DqiN2dQ44+9sg1X+PAO6K2{}^T`Ispg!LErwf}{>86hiD61*eCdWk-JufVYrDKiIhIhreEYym%1uj%g5W'
        'KAyoHv9;{u#lyveS@!6`qmSngemj?Oj<Y|GdMAPUPUO4U*I;)`dmrU+XR(&~LlGM4l>Y9&eI~9P@*rKy{BUY`^$A+KYC=+!kUo|5'
        'Wz1O#6*GSuRmCFsWrt?lp?7xheeltQ<L7a(_?nO{>StMmwwPzPP<PBAKLm~u<TPq8Gi>DCseG+&BcxZAsBOUc*=s`z$R2TbSrbK_'
        't^jAs<=d%~fD@ZU{GkFUtLLMyrMfo-5<?=15#57~W<hD|dv-+4s$%{i#(;vMrX<BRF}>XkBl2ly`91|Wg;6IPu}HQ}oJXk2G!z=;'
        '-L9z#`6c-mwL(i1WjxA&a9T!@X21t``7`D?4*YbpjBYeZb(ns-utzTTadYXkY2}t}^AR1$c0E|0E6~$%z=+|If21Hdxpf?KaR@Hj'
        '_AN@U{^{r^e{=kVjtlLjo3eOYHg}vnFeliRT61a%6kpgPB+y5Em}R_~v=zr$tjV&p#9dd86{^9ZG%-9un-$9?&=6&<#w~}sLG=mt'
        '_F_lSkHuCmi)~uj(#yz1l&>JwATk!&mpkDE9KI4K(@06kN-RhegqD`I>c`?KRznR0KqDhpASWo}FoHRTg(84+f>FA$YQLgG=}t(r'
        'eW6*Om^F^r-0M^lnxoc^;3`9U(g9gnc@=yQ<o-6r5P9^8g3zbwzKHe#9t6fiKtdO)`3&-H=>tVW%l4FIBfj(y<W8udvN1GAi9h;i'
        'K`3Y(0G2OcTg4g?LQokv=+r$PNADFVwS^V1qO;PEWNt)0{(5fc?~%Cg`tBIUOPT{sev~XGrT~F{?*j}23O5L6VF{LQXu|%9iVO|I'
        'AM8TN71~Oy6ts&FO)FX)P4$ouNi+@7<wHN#{EciF-i8RDRTNlQ3?`TQqJbgLV7M4!%M1%+&g=3Zm2N*x(Ac0&Ep5Y-V<FzHZ2JgG'
        '1=vLRixs9a{}}<K3^mTuS0lfK0_ia^OLfd&wEJ-ecsYtBYO4o1C~Aob(K?FIJ|HO!ZxQODdQHqTP$NpCT}3eQh^bCCBwDh2Q(yZC'
        '&do~2y$M%~&mJXTD9)N?Q>bLSt*kHxgigm+fjW5b^QvbZe1FB@vS<SH2APWLwfH2|x@-#6UK?Z*sC~+en)JHchU91wAA_AL#2-*F'
        'h0Z?4+Y=0U;6zrgBev393Q17)A%H?evI_FCfFAYg!W$vnjvqy3XqFsO1FYL#SF-1j1h02ZP;8bC43d$r4wk54-TGjUS?-F5N0}CY'
        'F3ngg#{pzgqqIiq%h0JBSH)J%`8x`^a7F+yhFVd`*qIfi6kWv_i4}hb(-q_GG~`9wGnD1g%zzs^$T{Uv2DDpRDp)iTqYVEnx7qwP'
        'eS&`9EMp*~uQpX(h%>`|U+rjxXi>4j$ET2C+F)=WjHL9GxY#%=c@O|KHU90KwO|1<&f+=D7RCC)32lU#!=GeCQIB+6rr?JA_h*o?'
        'SHv94zAP3ei#XiLC-~u~C!bhRhWO_!x3_Q~qw^5bamtMr%T%oA7-_(E5QJB88M`ep+srxzklT!&(wx6$K7iK64FUGu2oTirgou|4'
        '2`R1D7$dE5N~mO4TG{nlDQG+Qy2J<Am-t(3jV)D3zF2l`uSnlhv!JjFVvn#3!JKRq2s#B#h60$$*d)<y1b9$}>TxKpDy)h|t1z6V'
        'fC(h*iAusqGi8T#Y#L*Uj95)=m@ENBY0VJQd+7jZoU*D`s?s>bOhtwPo(!NUKjUcNUQ`<qrQMIO|Dd11OCyZ0tm(0hb<4FDs;M~@'
        '$yga;sZnbctm;=;3`HCfh$1yWk+xF^9dv(R?E3&8$dZ-OJNXg5qlOQbN`~C&sMF9F#AtY9B(3Z{a%iiH2Ii=4m!%owy3Rl_<wmxH'
        'rP<`(P{yFbp4~K5yTnc}vd9>ZF#^|E20>9Q2$)TLVMG)*Z}FmRzRJge6fQw=R%q61MVMS~RGXg+n{7S|Qwp5=0W|~*7{f?2wKg-T'
        'Th_a^HS}?m2V8NMJrCeh4ay?CYB<Vt%|TOH6z~9Rjd23#pg%a1kc89%#U{EO-IV<h7t*S{y6hDR4WMO69FTt?gEZ{B26798N=2t+'
        'A2ghbRq%(lxEaIpsRGf%&n<{L{cbCqTw0V!Bc)cw!b2x0K5|#!-$j^)#pa6PHjh8Klg%(51_GpevL$?V<T<PNTNBm=LuHNB3;jE2'
        '`biI?L+3<|w4%E#wTlHDm32~3JfcuhniP=0YjNCQQY-l#R8x=DdQ*U|P%P~5P@eoF%{xY`PeILzffMGXNO_b7>gKBBdGoI}|3-V#'
        'PC|_UI}IL|;Ux{x6iQ|Gcr$+#nT_g2b$_!@kdl}i!}dseSQS7lwT%D|#YBsFKN@FKC*rfBFBv-%(Xpfyi6GHBRAIsGuLI<@3x=x*'
        'j3vN6so^4mZY3^^7TB#;)U{oELl4$`JQ--1U)Wm{|L*YfV{Vx}6h^)4!MnZ_$56~~6mN^%)1uYl0@0$n>@1v3i<;QxIA>0^B9J<O'
        'Df4E#(E|_~9ZttO%se?ARFxhm5sRs6lF5EDx8^X(+xjQ0fW79M4FkSKDFV<6VdU^YG8+vdoQ4(md4&I_M+7T(*lPjOji^5&xW&*O'
        ';abVBm1)~<E4)ww!jK#Xr+VISAaLoE=_07z#^xEUR$_pSWg14i*^4)?f-g%(riq$;hA|mFwL0nZhG=Sb!J<2`-_+?r=n%=$wa`k;'
        '__qimA<BJGYDj6UkYa0<v)6qr`_#$~Se2_?dD4i*IF~<c@P0P#!!7F46(7-pvps0q04!K*2naYM%$Gz1WCG>kO*@xUNXgL-$h1^s'
        'McbtqwlEY6WCOmKWBblUt!}GsKbG`q;1w%9Wj#fWw{&w7dl0RfBHaKX99vBh!H4}Ri@u5$p_Pz_A6Ur6gvM9w{d9qyD7$&m2m($y'
        'JKhZ`f?r!joz=zurbF`@SrGD)?23l+EPz-Tiz?!nb+IE#*ygQj_`GREZCD2%*ezQB!>k^v!I!VzWck-(9G=PPz6Lk``MTZpZ`eOB'
        '&ral2F4}g$47cBtU%r>EUn~~c8F)^aMp#&^NbOA*5Czv&*ESn%FhUqOB;~;z4P(@V0JBE!;J?@p7FmqKX#P0Vkch&-(Q4F#zC+Q;'
        'HV`@#yKQX88B*(V_|U7%#tNIqx59xCvWuF)g1*`>?FN==FJE7@?;y#q+J2bF9!3UdU$6zi__hiWt8qrGglsC!xs5t2Qh)}Q#3DoR'
        '<{IQEQ^bo(HXIv^khI<?j7u7O)#!1mOI9QXvh2g0fQlH|m3gp)Ocgv`Vs)%Yb^y$4>&I2ndQDpj20$Rv*E=0!-eeCSJbL^f`{ggQ'
        'AaUfui1h<1OMe*}eI)%1Kj;&WlmY4QuFB>h=q*2b{^+?#Ir0D}q7GcF@K^66afZe>%q%)%q{e}goXpra4+#(XRWk<$+FFf_TW6)E'
        'i!_N+(MZ?tWis0HCH82sTDefGXP-XPg4hDZYAJtD%N)i1kD<>=5j49MK>_P=$mr{GxnHv94&<}RO;EEQwQ8{FiiwO-(K78(Fm|uF'
        '(4y@k<kF#O?Ok-jjA7J5T})a94#F+HHF5|7+Il$33F;AzPL#T|YwdN|DiNa8tS`|dExa?ZEBnXUU|bQqvV~dJdwm{Yp*SDZ2y#^+'
        'PoSr7l9ZO91%pC(<H(AwqAg;4aNa!pc=6%lBUwex_L^MFNo-j0L$6utT!>`1oy*JTijwT`)tJ_O^xI<<5P`pBao>UP0gQ_!-l}Kw'
        '=U;#E;;ZMUfURSddo3=pzCvUdB)U}zXvwJ_EW`zyps+$Mz~Mnt@Ij(Yfb%;oAC;$kDi5Z95$I;p&`D<fDtL=CeSC7ZS~YfCU6Eo!'
        'FbH)=gq4{3!Cc-Ud={P|)z0Vo+x~YC^Q4hYXm}a%1<J@Kv1iPsQRauPV&Jo`L~bH8*$!~6bpavwq5LGie4+fe7|;@P%o#87f_9}K'
        '!YHSOLa@sLe+C8}Sgty@pTvR1u)Q8kO_^f7Hn9>ABM&<$ob$#S1rE`-FgMxk+z=nK2BM`V+*T%Dqv>XCZ>{1s=-TZqRT|sDVF#;q'
        'G%aLj7TQa;ycR0I)XuW=L>nyR(|qCy(`#br$OJ^{b|wCkoha?8M9_*E0@9vyC9@Eq<Y8Ub?FD*tsOp`oq8(fK$x`jKY}wIzN{p;%'
        'PuRZo*8NAx$5;<P>SwXT$+%6W*cM$HgByZMvmp6h`@l4LGKFLhp2ebHxXxwJEwPDESI(o%;;hQmZG%wb{!f($)Q(Krx3E}(qn~Ey'
        '_e7~N=P)Osp5My@JjklE#}Kzz83gR=9`rG<!fu8(iAYhQ8>TvkiYO;m5bs^hERu(U1Q;V$fgeBxwyv@70$!<L8?o%L0Tvd@=W`DD'
        'I~iY?Z;r+2403ye#>;}?8z(RgUbRFpwKJ`x4a3LY#|8}Ph5%0p!-WdWRaIOztx6d!NS6&gr@I+*XKE10gl$_zhH>Y#wHAx4<2+F-'
        'H$9j9oS~GM^B)2VpY;{#9_rpj@fd2E05ppP!VXXgMT}Cdz0e*gMtw*6A5?0@a^tj1(0Bs5HT$EdnULbc#m65m9zZ+ZmgZs{ZEvZ-'
        '^Cq=?YH=k^39CFBjf5lmvvcd*b&?~&VG7_l3t(nFHuR)mvXJ=z_HaR}sTn=FBqGROO1HReVeXeOLEsCcQtMt<=&Irw^dYrs>}>_*'
        'ff0h&tgSurbzQvOTTf~ocPu&pJ<2-veFj8GGr{4EC#j{scor|>cor%=%JJ!|<_moG4L-_`pNy@JbsjLb@jV9IHA8AI4`YG1PJjU%'
        'LPh1<C<Syk4(+7LagM~G`~7*<A%u%#R49)@`)<wmyg7(d9@30>(Uzakcq*`e7Q(Tkw3_tPNeT82f-_nCzh7j}-+WcUy9(bc3hY!f'
        'QW=o~1G=+}zd$0*zUBxhczr`#Nq<AqnEc-_(6webN&2$sX^mqZhRE>DVGK*otZlm|V@AIz2Sp()HTw9z2p0y!vSYX}ivbypqKuEK'
        'aX!vF7^sIXR<avrKZYj~3Xo5u^OvXle+v96Bj0n@3fUoK*A<f12&g?74OBgl^ykE6@K93Bo_43y?tcx<zA?0(_S>}9Lc<kvdzC`5'
        'HJdakM9Y^I<7daGnxKaakb_NzIx>tZ_1-C0HnSPcMk<-{@Pp(q2va<p*{!WTp88kxRIH&CTRRrpYK4wgD;6>weUd%O#LnoCV@?c^'
        'zgRVXluxm#2TNjc0?%9x^=-Xl?Uxue2ok&%=Srhs&#pu{R=bTFs{q-fT)`~=-!1Li{5Yn64{)9qVmngU?-3?<d>U|j2NPm%m}H+h'
        'wSe1>U9>_I-E^a5=ez1%jQA(wa@^&Uz*j0Vv{6cp7;kiFVsgf$3e6qj+*0X+zV5MAda!BW&4*Z$!PmZhVQma1fU;iwr(1ql9^VEC'
        '_`l6fi<eM@UL2u_R0aFlYhCm$FhuC5Fu6?va143@ilU};3z4@MioZB-CK3FqiO@gJpEdm2(x5Bjod$;O;SZ3Mo{dm>xc@3)HAk=a'
        '3q+)ib*_up!mx}KTLOvmo<&Sd34?}@_R3sUWNuAx4m-Tb&_M^i8PR`Z7wF_e+)h$h=eV&&&pft%FY42Snv_7w=;LLbE&^6=u!KB)'
        '$^MS6j8iyYb|;!I>FB}UDSd?EVe6lyz2>vfYTi(F=z>>I`}IbwW}tU2vMy6tq=n<dR-oKi7WI$sMJ4_?VDa1FV@%s_4l#q9c9{)L'
        '20~u{iB)1*5F5ylaj`4HgOZ8IjT(`cNvdvy5$eq(p(nIr+;?@92Lxm*XtKRE#c*RudVR;tAQv=Y&zlkVXy2bkl<U}3GGk9k_WnXL'
        'P21&NQ@6Ag(dL7)AF*p1FoT5b-%g;p)_WLfn1VKMSXG=m%JHGO7TF(&-XI$?1f6<VK;s7~eQW-`R;{T|D2`0cd`zftw+4z#0~j0t'
        '@+g2MZPZO{w54@${96P6J+lmu`!!q6SrzQ9Y0R`)$~B|Vhv&jN5_VK%rpS<#!HtcL$(N;B>Q*ZuL~(DH-Rp0v^?>V^{4x{2%)~D<'
        '@yks7G84bd#4j`P%S`+-6Ti&FFEjDWO#Ctvzs$rhGx5tz{4x{2%)~D<@yks7G84bd#4j`P%S`+-6Ti&FFEjDWO#Ctvzs$rhGx5tz'
        '{4x{2%)~D<@yks7G84bd#4j`P%S`+-6Ti&FFEjDWO#Ctvzs$rhGx5tz{4x{2%)~D<@yks7G84bd#4j`P%S`+-6Ti&FFEjDWO#Ctv'
        'zs$rhGx5tz{4x{2%)~D<@yks7G84bd<fkt)i5(RIVAHln>=hT%BnA!+-G-w1JvuY_;vFC^c$iOBmxy@d1!^UYWsz;fEsjsyJ7a6H'
        'r!;h7H&Da(!c9xX2VNKiau!R|i8Bagf=X_v9?<$s)Mv}jH}-&ayR%Nav(z6u?3(ruSWenQlIxRS$7!E81V?`G^*(#L-F`4`fc;iq'
        'rX5gq67jbpeM@L+C86_s0h#@~>eZX<O(lAaJ(&P9`CWB(1>@u4$LIGZ-SnTmu(o~OF0?Vy`&X82KY#Rbt{v*~YKzD76ZxZn$RFR^'
        'XX=r%PMN8uv8=xja}W{#?dLB(hgx7KIy9L&x~@czyj!weX|-7nwSq;h#dDwKf7|k^)$cwLreA%EUc`!O<GZHCUs=v=m`r_UMFnx1'
        'gw)XkL|%B;RN@l`!z`)HwBp~;D3YJ+Nq;FP`DpR@qs8Ocf=>l8E7E1-TLU~HyR+GC!b4Wpa%vCfynZERp#=^K8K$~L_MF?KJh<D;'
        't=`;vg=nAYv4;`qag1PyKZ~}w2K={ooHt;qq!l5P!pyW!rtxG9a#Jn_r@f!@G2zX8D0^17v7Uv5&LvxXejH58fr{(4LI>?)oSD^U'
        '(g{vYt61buoprcfF=RL1_A-xcP-L((Rp!<JFz1%p8E9T*7s|QE>uj`uW5o*JFqEhTppV|5Usqbp&BE`n_hnP46*Eo-Ep6H4E6++{'
        'G!_qqwxgptIn(Sd3o>a;fg?JxZdRWcLvbeboyT&%<RLalBv&Rr#l#{Aw{@f%Ni!I<Dx*(&)$;I=-$UgCUp;4$Fu_#jWCXuL<*_z)'
        '!z)tn&_q99WLL+G&HGa?FHVO+Tk9&Ndu2(R3@x#jJ2@<|SQdHWrXdsoFsvr;6Elu3#1L}WxixP5jDRiO#sJ<5Vf-I4mk&%UR17aQ'
        '%fHBuc%PCnc~YWcX|X(!=-SO1l&c)^=+|kY>(Or)$9Lq1^sc24L(Y5l)W{>V!=*jdLUG|;c3w)FqtxvsRNJMJf&m?3Jp=;eu?jTl'
        '0$zxs0oeNMr?3C;{F@gqzx@7>&tJcJ@#>{QR-S$P`t|dd-+X`e`qke*fA&rM(u|R7MY*ZdA{uj{LEbw?i@nvDJWXzq(suE>X|Od>'
        '%c;I>%dX2g^Or;b^eQ-~*~htE#{eKpZjHXRYEBtPF#xnvr$bS)M1%<9WgGM|Sq2~+i<sWK0q2eS(-tBafu%BNY!Jd#&70lk0x9)D'
        '_~v#$>^pL)4<9ZbQH0p}vk;`b6cI&vDpS<Gw0?}b0f=Y|xfXXe!~P=X`YhovwnP^B#R3!rTA+oFrrgM8*eOfS=Q5p2B=-V1Iy68m'
        '#;(lP>OA%gwwpvIBi_O0^Lf?GHK4S}Lj*J0Z7^n41mol^L;g2UGT!YHd-AIE3zxHv_z6U#t4>^oYj%kW2~spp(1!j4S_>XEE${kK'
        '5X8wzmd<3Z7A-rskJfCG^3i^j$JiG@Fs8jHv_cRhzDNg+R1K$qD(MNbQ`Xv2PVff3rnJG$qzUJ2Wb|SP`L%@gC|V1+g!_mIR4IRQ'
        '_L>s9f+`CTDBP>T<Pb9HB6PQiCk$h~jd#1XWS-8|o7{Sn+n;Nb+rOgAtscz1)9f$zt{(vC!#_dT^B;pBXk*;Z4)OcuWQ;%>g`*oM'
        'vwnjk&>7bfLSBK$=gZaUc#KnIg@#)-r#ia>o{@YPFW_Jt@B%?GR%*hoY!}+fgHkqJi8GRwPEixc){udk#V{czZg;)%YD9R5D`SFq'
        '#EFbZ929<s9u@5cqGagg!^|P8y-5%#roPqMgSFY{oV8@=-O9-L)g)-P$UY}QT8}QkJ;a3j`<=`YRz~3ehY+?2T1pXdU=i(ov$}@V'
        'TN%bXZhcZcK&Pujor>k~?y!y#LRW)JUZEwY(UsHBL({m3K@1(>FhEk&MAV8L;gOKFP=}c=0T*W#f-&;=Bukp`Me987U5q;u*Cm@?'
        '(8t}gAIW(G_wLQ_pK2M`hZpPB!}WvQ@Iasyqt&=af!V7;i%+KCYjBizyiw995zMSIOSiRc4$*7cMJHfuEZ18S25(`_8W&fv8L-7z'
        'EEQA?<Nd3U0#LRhcCZPDNHD{Dn(VrNKhUcoLxG#wkNl%iOc*Zo?{Q<}h1OA_(T9R~^cK@q8~R`U&|at`!v$CszRbF)cNA*I3gfrt'
        'Icq;&t8c<xNNUc-=m~pjTq_yI1)W;*w;b`qp+0JD35|Yw_faU^4+YHCHt@%za8K3rqApDXM(qoaQEy$)dxq3G+4o~L1PN(dHH}*9'
        '6fa$M$p*N3c-vx+5E6xSxKd<nM9t6(ZvrfJ>Jx>f9i(&(%*B2enlWg<pK=w8$WL+K?g;V8AvC`?p(z%(c9o9h0CA2nJdLQW_&hL>'
        'EpEi9K{>Ej^>n_rbZk4G)xA4!G-s$mxHgtx3}MRg?l4AHk~^ngwqyOg?K6Hqc8jf=&;r&t{7I%_Lc7DZDj3QvnZS6zSuvj7Jl<n*'
        '_Zf-nm*#l;x8vn$?2<9A+o00&`L5#=`n`=7T8AVpWJR)dY`VN-LIGhW8T^=I8A*O<)z*MyOvVfF5lU~9I@*<qLL}PXSGSHQ#GJ#v'
        'F%Dc4s-kcftsiKXT4ckXD-5&_#b&Dw%7wnI^6*eBB2@W!_0exWTz*7<=)uRQ4}N|6@T2V8Z=Nv|_w+VR-M|0QW88eRgMNVK>h9mq'
        'j&M33K6v!_@y8#1^wERg&SIKd#(VJa^zkDMISZ%2^xTBJb)SyIO@Il_ZgKXdwi2~_)QoWR)o*|O(QhCARt3LF4-Wls`O)JCj~?dP'
        'uSV@LRTCr82gy#}V9Q8dxZQ&qSN-r|Ty-c!EQWOHAAR`v@uOe=db0F~AD+r{vh?G0O^SF8q@-(EKPbxeZ_3G9lEeAc9rI5TNpD)='
        'x5}CaucF{PO{5&&awYq4*|MfCc|X}>Kt@)mc0Al@o1q){AwfqV;YhO37@)-cO|eHW7P!gmxz1>`H6)9c!Knq)&c~Vb2eYk<KciW5'
        '5O_L?JNU``aj?@MLg7-wXXC&ILZo33z$Ydy!aDkd)Y6BzCPV%xvFij7|6nV6>$yBNnPc_;XSY-#8k;FjWePc-9Vo_e8)ByaKrv?7'
        'ZPf_GKFU!l^*B!cB1<j1zn=UB|NQF-I8Hun{wg%|zy7y8hj)Ch*4y{}RS~k|)}<?SPYbUP2LUZ56Ekni1SG57tvRB0U*c1GF_k72'
        'c^BYFL!n=l>dd74Dk-kg)0UUvu`-zG>k(BSFB1$c#DwCeFdv1}g!>x<#;7zCH<Uz)?@fPJi<8d2{U$s4@hv==JkL@hP0mdY;MI38'
        'pT9nN{rv2eJ^6C_TsHrQOkS2Bqgm)ydxWt_kEc)Tw;+5(%O6Aa59Apom^Nh20d%_(v#<JdnFkIrS~(z+aE4FMUT8CK=Gz00S}knC'
        'rVQ8I6lzNu=+BI#yKMET(Cl}(g#gCkD}ziOI3KnNV>zF$JHWQWOjJ`{5KAdO1K$~J1M?76q$YW_=(Ui9nJp1P9TfFr^{p%+m0PpT'
        'Jn3#8D=T{PX=;@}37A7O<*k%go7EYz9ejTc>z>-1btq-hjh@@B=DMP{n$nzx4I!(=dTb!_Mkj}>+VX8TXC;PW@HB0AsY9uWF4nvV'
        '^6RqJ`kiWhn*E)k6yaVRSq&TrNL257mVIy#_n&`otP$v#SYn_`)v`&~KFNicDl4mN>rThsgyC}6T%!V~BQRo?Z1HJma+*(010QC*'
        'AhS2fV=Qu6WU*?B@-qe^?6^-SGS%h~Zk5oT%d<CscyV_2{PQg6Kh__9_5A5e!ydg%&l9^|t*4uz2Oc(KrVU`ix-E2iyRs+TI+9sn'
        '2jM=bg!}i6R+3U*^Z4{d<OvIeATE8Sx2h&Fr5kHv8N)c_V^qtUB@+GXPzRJ-YvaY2FTVNxx1W9g&8t5=f0<`T+A}Jiv#czvy0-$k'
        'V}*=a0}0yfhdyh#0;C^{uoRyJwu<(<<<g#Rx7JmFJtY^JUe3&>d|4KY#}9mO>tAQBB6}i@c3Vme)a;H|%VK6){t>+Rw4q%P2Oll6'
        '-^;OyOOf2K+$(C&j#gh_8j4JgXKfMDfZ<t%K8i8+asNI{2fY>^yU)b0-m@o0=l%O6e|<r1;C%G8#dV+g7f)Y&_3i8D2e95C)Zcvj'
        '?Ah}-Z}NC+lwFO4v16~{5Hql@&9BVwoY{3i)V8Zr4VWn@v3@c;$?Tp@n2q5g-W%M{aTPbK-bX%CCeqAqI!WP*$qnSP-yf^hl;%5#'
        'cWTFb<i`-@B)c-ACFRFS9aSu!3im-}xuxK~*J$D?0@<2FV%;0#f0LUnV|7tzov6wv*_H!B=iM&cV_w-C0nb|5IAZ1dVTT(-wOOiW'
        '?+dk=6)?~9QC%`M4#bq#7$UD|KAss1hwaGd7NK7!b;ZL7NxapjC2`fyn@6!xBBfkWb)o0UdGjG-Dw<hH9<Mfbl>@x;C`^>rRIVwm'
        '=UWyLFasFeSz29sQOk814!J{?Aa>S`d=mE;WpL;Bet@8f`M0yz=l4(w!yQTMPs1>*ybmR(+9+(Jt$NFGO4`o#vPFwhwd>h34Xr~V'
        'wONUcN>01|BXltp(%2LY3w`Ud9OgH`Xk4}Ed-_d#d0AWKSlsUQ+H^ZBAN8JL-enW6mlC7v36i`@!jt+x@NHQU18(f{KXw(7McO;J'
        ')p7|9wnmKHtsWH2YkorO^;4@72%RZRO38fq*Bi)%H+na;Ds0N&*OW*cc{FIJ1D*s-;0cK9B&}8bv8U7&mTBH;4D&i;rSxFZ51L>I'
        '3{$IVMMNI6BG(TVk319NnGnx}cqYU%A)X2GOo(SfJQL!X5YL2oCd4x#o(b_xh-X4P6XKZ=&xCj;#4{nD3GqybXF~qVW<oynOo(Sf'
        'JQL!X5YL2oCd4x#o(b_xh-X4P6XKZ=&xCj;#4{nD3GqybXF@y^;+YW7gm@;zGa;S{`LCA=nPr;&xYg=yj$LY-nEZJ2-fnVgrGaOE'
        'vcX=`J1%MR7UDOWP0`MMX=^#V|K+L-H=^kkDL>U@?!0+_m$_TL<SOmLeXH?Yul>-&l_k}N*Z=WSq}X>*%uOgw?bx=*r?)R&nuTkZ'
        'W_Dd1x@We$pO-PaqMl!flwt^?7>d~1Enc?}UG32K*4l)s7t+>dH@yE=CfpJg49SD$gt6<OUTZ^3%o-BD?*=OJczOj@mfS!!_9PrH'
        'qq5C<t&<7ci%-qXFJw9@>x$$cX4+n~+vp@1AmuffjRlc$X&7Y!J7S+V@@{LiKffqO#m#ZFXKjNhu{c75_Wjc)mwEwDv(ogMuC3xV'
        'r4-l`atv`?n@4(eL+JhZn%TDGqj^a6jV&aD7)t0KeW$Bl+nzT+Lh*W&NX5?jsw~--)%xqn76ev|Jt3)a^m?bzy|?U=E`w|dnf>F_'
        'FQ32s<_$YQE*2;8U)IPq`{a|eubzJM#jDp}fB)sTFFt?z^4arGKmAcD0=w&nK1h*YWG``n^bfcIkgYZ6+}N=ncW;;S9qwq{bLQ@1'
        'W6rphQQC|*<0LX<AN_d}Nk$r3h6Jcm3)xP?0^$CYKHdO^j?KevJGoOZUN&X{mxA{+RLfmmba8^n+s(pB&%{g>Q*TBh9lKbb+I1M#'
        'hB0ZAtT%r%v!>qdLQ{|=mC3byW*S4?*TtUqB-wS9cIiVPc<rw}o_lOh8!q{2OvZ`gK9DfhdK=SGUM)vCI`VV4GUtHoWd=1HT>k`R'
        'FMgDo*p_xACU)gLv395bItsFf{?iiB!ThFlgl_5A75cdT3<;?&cC_xxfxVu8lA0pc<KcfS*5d%i!Oi@e;2$Z(BLl)i_T~`cVK0v;'
        '4{GmbGQWr&_$h#geR1CW?EsG#Nuy$GX|5^!D*98&W``L6fkQa6JB1O`c=5R<P&E9!ZRK$HvGYA+C>OXtPt=~JU=F!`VE^l2c6=5h'
        '8ucE;*)|h@qdSPK;-P2J>?m&q%EntBC->~m#?Q4qasVNi^%`9IXD@Jff|;xqDYGmIJMPlU;}KVEy)HsC%8K+NKfNAY!81+3UW6Tx'
        '{Y~y~4Thhd2=;%L`0oc->&63MIz!t|hs$LRrGs_r0fLs*zYog`xfcqO5ZKjh>-0s7I{-BdaESqUB~Q&U*_Fk&HZb&7!P}j53jUx^'
        '!eO(Bx3FlPu;V05m!_Q1dmXeCZ)HzO=vw3&ZIk@<^RJ#iee?YLGyTuAuU?=f|BKIay(vYbfwzA4^z7{WKRo}R`4bDdC|js+YUw`Q'
        'LB=-4Gu$06J6?$@DB1a4?*f|avt`SIh)gc4hJ#({ZDjQ0hj7t3Zn!u3-JkLniCi0S+jhqIA-SD5T34DcI5-z#H~LgWAjXp<3}xHJ'
        'j#kQ;N5TkR)FLtThj4%29q~;7J4Tt6TtQ6Rzqc$VuZRj4h;|WfRm9s2LXb1E-mPoHyK)Sfw~DUN7><L-96aXWF$a%1c+A0L4jyyx'
        'n1jb0Jm%mr2ah>;%)w(09&_-RgU1{^_WwC}?5Sa@6lsOD6QsGN$vJNxJ@#>giKXb2|2T|TjC4%Q)t|B~(g2z+?a!83;Z66za1qUw'
        'hBKqc8AQA9#IgXbk2f=Kf{h*S^Hfw847gQwU9A9v2#euOc#uFkPgq9Su<T-wqtPVZZQvdlw`n)+uGeb|xz(BJX}!%^g`*`$WPWA6'
        'Mhc-Ux;|)a8t+X1kP<sH-#4(QE7H)4WY0UjM^Dd8Hrzh1)S>V@3p2!X47+KCxla+sv+w41VdW|tF)YdIg5w|pEx_+mPyBYiLLGr7'
        '-aig5(76VGf=<d4BJ?zrVYv^43hF4jEQ1x8wtPp_iC9~N?-9}=92!t(gJsl0SkZ)=@yf=0m6?%Zgan$~!mZ|SWpuH7bk^m2uz^pM'
        'AVnYw4OvomV1{UpM3>zREq2UwhyJ!?&LRXewyc}BRBv1F21^<g^$kOFVgL)jAEdo_A2&Dx!Xr6Pr93-JV)YPHwH+k~EL%oO3cKzx'
        'gflH!5Y&piNo-X){QoqVy=@ot)_ccxY@cKM9NXvEKF9Vsw(s8y+xG>t2Ag8}>P^@-D{X-9meUbgmDd_AoDk5YM+)#0JNPhSSJYu+'
        '%rK*lhZRu0GhK3B*6o&He_M=s@4LD}ENI?j4<9^w{2=?~FLNZ3l62OU3_rTZMQR$z`SWXv1G{~mD?xBvetX@bJmWhQuWW^vv;6tj'
        'U%dEAoUPyjnk%9&0eXn}Fo+)rM@?S$d-?AMxPP3a>|g|z1sbHxgUt>m5W}vU*VVdQ?w55L0Bx{?=jFR{skYFl`lc6er?+S)8}E=z'
        'hh#b=^WOx?eEc8Xe#;@54#{*#rb99vlIf64hh#b=(;=A-$#h7jLoywb>5xo^WI80%A(;-zbV#N{G98lXkj$SCB=Z;9n<Vxf8-z8*'
        'CU_5BxzkWb+>VgD9QQ}#L(R1;hA%mIB0K7LvbQ2i^JS%+E05<>{?pIl{@~3-M)D(JN!u??@b|&)x^vcuU<L#tdzCQ|cWOwY^X4yj'
        'f$W?Ji@#<k*<a#Z@qztDR|gdWS7D}+pEz@&BXK))7UN(#;nQ592i%E1O9z*=6Xj_?$;(Hj{3-fmTxncrS6(7I)b&ZfzR*05yEui7'
        'ay<J;h80>q_yn<k`JFIx479F}5kd$(<R<Bl@i&;BP3d-@Jo3VZ{RkNkR;*tBqZ^#dt4NcFVFGORs;Hq0u$eqaaPDM(97XIXVn-1>'
        'ir7)ajv{sxv7?9`MeHbIM-e-U*ipoeB6bw9qlg_v{9hhL{E?%G9YyRYVn-1>ir7)ajv{sxv7?9`MeHbIM-e-U*ipoeB6bw9qlg_v'
        '>?mSK5j%?5QN)fSb`-Irh#f`jC}KwuJBrv*#Ev3%6tSa-9YyRYVn-1>ir7)ajv{sxv7?9`MeHczpB;+$p`(Z$MeHbIM-e-U*ipoe'
        'B6bw9qlg_v>?mSK5j%?5QN)fSb`-Irh#f`jC}KwuJBrv*#Ev3%6tSa-9YyRYVn-1>ir7)ajv{sxv7?9`MeHbIM-e-U*ipoeB6bw9'
        'qlg_v>?q=&8H)Ikqlg_v>?mSK5j%?5QN)fSb`-Irh#f`jC}KwuJBrv*#Ev3%6tSa-9YyRYVn-1>ir7)ajv{sxv7?9`MeHbIM-e-U'
        '*ipoeB6bw9qlg_v>?mSK5j%?5QN)fSb`-Irh#f`jDB_<PiuglE5j%?5QN)fSb`-Irh#f`jC}KwuJBrv*#Ev3%6tSa-9YyRYVn-1>'
        'ir7)ajv{sxv7?9`MeHbIM-e-U*ipoeB6bw9qlg_v>?mSK5j%?5QN)fSb`-Irh#f`jC}KwuJBrv*#6L3>@nc63JBrv*#Ev3%6tSa-'
        '9YyRYVn-1>ir7)ajv{sxv7?9`MeHbIM-e-U*ipoeB6bw9qlg_v>?mSK5j%?5QN)fSb`-Irh#f`jC}KwuJBrv*#Ev3%6tSa-9YyRY'
        'Vn-1>ir7)aKQk2ZM~)(P6tSa-9YyRYVn-1>ir7)ajv{sxv7?9`MeHbIM-e-U*ipoeB6bw9qlg_v>?mSK5j%?5QN)fSb`-Irh#f`j'
        'C}KwuJBrv*#Ev3%6tSa-9YyRYVn-1>ir7)ajv{sxv7?B8J}6>^J)Fo%oz$YU=E9IgGmk7b-xS^3l^Dm4Gj^P@<BT0=>^Nh`89UC{'
        'amJ1_cAT-}j2&m}IAg~dJI>f~#*Q;~oU!AK9cSz~W5*dg&e(Cr|Nb~*B}2y=JJ#5-#*Q_1tg&N_9c%1ZW5*gh*4VMejx~0yv15%L'
        'YwTEK#~M4<*s;d{39-h1{p<e&DkTLs'
    ).encode("ascii")
)))
# PR #53's docs were captured from its since-deleted branch; they shipped
# unchanged in v0.6.0, so the fixture history tags them as that release.
_LEGACY_FIXTURES["sources"]["v0.6.0"] = _LEGACY_FIXTURES["sources"].pop(
    "origin/fix/lint-clean-generated-markdown"
)


def _render(repo_type="python", name="sample"):
    return bootstrap.generate_files(
        {"name": name, "repo_type": repo_type, "postgres": False, "scheme": "App"}
    )


def _git(repo: Path, *args):
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
             "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"},
    )


class ExistingRepositoryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "sample"
        self.repo.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def _git_init(self):
        _git(self.repo, "init", "-q")

    def _commit_all(self):
        _git(self.repo, "init", "-q")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "init")

    def _write(self, rel, text):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def _agents_missing_a_section(self, files):
        """A lossless-to-rebuild AGENTS.md: the template minus one generated section."""
        generated, owned = bootstrap._split_project_specifics(files["AGENTS.md"])
        start = generated.index("## Preservation and destructive operations")
        end = generated.index("## Definition of done")
        return generated[:start] + generated[end:] + owned

    def _legacy_templates(self):
        """A disposable tagged history built entirely from checked-in bodies."""
        repo = Path(self._tmp.name) / "legacy"
        repo.mkdir()
        templates = repo / "templates"
        templates.mkdir()
        _git(repo, "init", "-q")
        for ref, sources in _LEGACY_FIXTURES["sources"].items():
            for path in templates.iterdir():
                path.unlink()
            for name, body in sources.items():
                (templates / name).write_text(body, encoding="utf-8")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "--allow-empty", "-m", ref)
            _git(repo, "tag", ref)
        return templates

    def test_check_reports_missing_files_and_never_writes(self):
        files = _render()
        report = bootstrap.compare_repository(self.repo, files)
        self.assertTrue(all(status == "missing" for status, _ in report.values()))
        self.assertEqual(list(self.repo.iterdir()), [])

    def test_adopt_into_empty_directory_then_check_is_aligned(self):
        files = _render()
        actions = bootstrap.adopt_repository(self.repo, files)
        self.assertEqual({a for a, _, _ in actions}, {"wrote"})
        report = bootstrap.compare_repository(self.repo, files)
        self.assertTrue(all(status == "same" for status, _ in report.values()), report)

    def test_adopt_keeps_existing_non_agents_files(self):
        files = _render()
        self._write("README.md", "# Mine\n")
        actions = bootstrap.adopt_repository(self.repo, files)
        self.assertIn(("kept", "README.md", "differs from the template; not overwritten"), actions)
        self.assertEqual((self.repo / "README.md").read_text(), "# Mine\n")

    def test_adopt_rebuilds_agents_keeping_project_specifics(self):
        files = _render()
        agents = files["AGENTS.md"]
        mine = "## Project specifics\n\n- Never touch the billing module.\n\n## Local notes\n\nKeep.\n"
        generated = agents.split(bootstrap.PROJECT_SPECIFICS)[0]
        # A generated section the repository lacks, plus a repository-owned
        # tail: rebuilding is lossless, so no opt-in is needed.
        start = generated.index("## Preservation and destructive operations")
        end = generated.index("## Definition of done")
        self._write("AGENTS.md", generated[:start] + generated[end:] + mine)
        rows = bootstrap.compare_agents(agents, (self.repo / "AGENTS.md").read_text())
        self.assertIn(("missing", "## Preservation and destructive operations"), rows)
        self._commit_all()
        actions = bootstrap.adopt_repository(self.repo, files)
        self.assertNotIn("refused", {a for a, _, _ in actions}, actions)
        result = (self.repo / "AGENTS.md").read_text()
        self.assertTrue(result.endswith(mine))
        self.assertEqual(result.split(bootstrap.PROJECT_SPECIFICS)[0], agents.split(bootstrap.PROJECT_SPECIFICS)[0])

    def test_adopt_refuses_local_sections_outside_project_specifics(self):
        files = _render()
        original = "## Prime directives\n\nOnly ours.\n\n" + files["AGENTS.md"]
        self._write("AGENTS.md", original)
        self._commit_all()
        actions = bootstrap.adopt_repository(self.repo, files)
        refused = [a for a in actions if a[1] == "AGENTS.md"]
        self.assertEqual(refused[0][0], "refused")
        self.assertIn("## Prime directives", refused[0][2])
        self.assertEqual((self.repo / "AGENTS.md").read_text(), original)

    def test_adopt_refuses_differing_generated_sections_unless_asked(self):
        files = _render()
        edited = files["AGENTS.md"].replace(
            "## Definition of done\n\n", "## Definition of done\n\nLocal edit.\n\n", 1
        )
        self.assertNotEqual(edited, files["AGENTS.md"])
        self._write("AGENTS.md", edited)
        self._commit_all()
        actions = bootstrap.adopt_repository(self.repo, files)
        row = next(a for a in actions if a[1] == "AGENTS.md")
        self.assertEqual(row[0], "refused")
        self.assertIn("## Definition of done", row[2])
        self.assertEqual((self.repo / "AGENTS.md").read_text(), edited)

        actions = bootstrap.adopt_repository(self.repo, files, replace_generated=True)
        row = next(a for a in actions if a[1] == "AGENTS.md")
        self.assertEqual(row[0], "updated")
        self.assertIn("replaced: ## Definition of done", row[2])
        self.assertEqual((self.repo / "AGENTS.md").read_text(), files["AGENTS.md"])

    def test_adopt_refuses_to_modify_files_outside_a_clean_git_tree(self):
        files = _render()
        original = self._agents_missing_a_section(files)
        self._write("AGENTS.md", original)
        # Not a git work tree: an existing AGENTS.md must not be modified.
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions["AGENTS.md"], "refused")
        # A git work tree with an uncommitted change to the file: also refused.
        self._commit_all()
        self._write("AGENTS.md", original + "\nUncommitted.\n")
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions["AGENTS.md"], "refused")
        self.assertEqual((self.repo / "AGENTS.md").read_text(), original + "\nUncommitted.\n")
    def test_adopt_refuses_text_before_the_first_heading(self):
        files = _render()
        original = "Local preface the template does not have.\n\n" + self._agents_missing_a_section(files)
        self._write("AGENTS.md", original)
        self._commit_all()
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions["AGENTS.md"], "refused")
        self.assertEqual((self.repo / "AGENTS.md").read_text(), original)

    def test_adopt_refuses_a_duplicated_generated_heading(self):
        files = _render()
        agents = self._agents_missing_a_section(files)
        original = agents.replace("## Commits\n", "## Branches\n\nLocal duplicate rule.\n\n## Commits\n", 1)
        self.assertNotEqual(original, agents)
        self._write("AGENTS.md", original)
        self._commit_all()
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions["AGENTS.md"], "refused")
        self.assertEqual((self.repo / "AGENTS.md").read_text(), original)

    def test_indented_project_specifics_line_is_not_the_boundary(self):
        files = _render()
        agents = self._agents_missing_a_section(files)
        original = agents.replace("## Branches\n\n", "## Branches\n\n    ## Project specifics\n\n", 1)
        self.assertNotEqual(original, agents)
        self._write("AGENTS.md", original)
        self._commit_all()
        bootstrap.adopt_repository(self.repo, files, True, confirm=lambda sections: True)
        result = (self.repo / "AGENTS.md").read_text()
        for heading in ("## Commits", "## Skills", "## Project specifics"):
            self.assertEqual(result.count(f"\n{heading}\n"), 1, heading)

    def test_moved_next_dev_block_is_reported_and_refused(self):
        files = _render("nextjs")
        block = bootstrap._nextjs_rules_block(files["AGENTS.md"])
        moved = files["AGENTS.md"].replace(block, "", 1).lstrip("\n") + "\n" + block + "\n"
        self._write("AGENTS.md", moved)
        self._commit_all()
        status, rows = bootstrap.compare_repository(self.repo, files)["AGENTS.md"]
        self.assertEqual(status, "differs")
        self.assertIn(("local", bootstrap.NEXTJS_BLOCK_MOVED), rows)
        actions = {rel: (action, detail) for action, rel, detail in bootstrap.adopt_repository(self.repo, files, True)}
        self.assertEqual(actions["AGENTS.md"][0], "refused")
        self.assertIn("back to the top", actions["AGENTS.md"][1])
        self.assertEqual((self.repo / "AGENTS.md").read_text(), moved)

    def test_missing_next_dev_block_is_restored(self):
        files = _render("nextjs")
        block = bootstrap._nextjs_rules_block(files["AGENTS.md"])
        self._write("AGENTS.md", files["AGENTS.md"].replace(block, "", 1).lstrip("\n"))
        self._commit_all()
        status, rows = bootstrap.compare_repository(self.repo, files)["AGENTS.md"]
        self.assertIn(("missing", "(`next dev` block)"), rows)
        bootstrap.adopt_repository(self.repo, files)
        self.assertTrue((self.repo / "AGENTS.md").read_text().startswith(block))

    def test_dangling_skill_mirrors_are_reported_and_removed(self):
        files = _render()
        mirrors = self.repo / ".claude/skills"
        mirrors.mkdir(parents=True)
        (mirrors / "retired-skill").symlink_to("../../.agents/skills/retired-skill")
        (mirrors / "elsewhere").symlink_to("../../no/such/place")
        self._write(".agents/skills/repo-skill/SKILL.md", "---\nname: repo-skill\n---\n# Ours\n")
        (mirrors / "repo-skill").symlink_to("../../.agents/skills/repo-skill")
        self._commit_all()
        report = bootstrap.compare_repository(self.repo, files)
        self.assertEqual(report[".claude/skills/retired-skill"][0], "dangling")
        self.assertEqual(report[".claude/skills/elsewhere"][0], "dangling")
        self.assertNotIn(".claude/skills/repo-skill", report)
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions[".claude/skills/retired-skill"], "deleted")
        self.assertFalse((mirrors / "retired-skill").is_symlink())
        self.assertEqual(actions[".claude/skills/elsewhere"], "refused")
        self.assertTrue((mirrors / "elsewhere").is_symlink())
        self.assertTrue((mirrors / "repo-skill").is_symlink())

    def test_wrong_type_is_refused_before_anything_changes(self):
        nextjs = _render("nextjs")
        for rel, content in nextjs.items():
            self._write(rel, content)
        self._commit_all()
        before = subprocess.run(["git", "-C", str(self.repo), "status", "--porcelain"],
                                capture_output=True, text=True, check=True).stdout
        files = _render("simple")
        report = bootstrap.compare_repository(self.repo, files)
        self.assertIn(".agents/skills/local-validation-nextjs/SKILL.md", report[bootstrap.TYPE_MISMATCH][1])
        actions = bootstrap.adopt_repository(self.repo, files)
        self.assertEqual([(action, rel) for action, rel, _ in actions], [("refused", bootstrap.TYPE_MISMATCH)])
        self.assertTrue((self.repo / ".agents/skills/local-validation-nextjs/SKILL.md").is_file())
        after = subprocess.run(["git", "-C", str(self.repo), "status", "--porcelain"],
                               capture_output=True, text=True, check=True).stdout
        self.assertEqual(after, before)

    def test_type_check_finds_another_types_skills_wherever_the_scan_would_delete_them(self):
        simple, nextjs = _render("simple"), _render("nextjs")
        skill = nextjs[".agents/skills/local-validation-nextjs/SKILL.md"]
        padded = bootstrap.read_stamp(skill)[1] + "x" * (1 << 20) + "\n"
        late_stamp = padded + f"{bootstrap.STAMP_PREFIX}{bootstrap._digest(padded)} -->\n"
        self.assertTrue(bootstrap.stamp_is_valid(late_stamp))
        self.assertGreater(late_stamp.index(bootstrap.STAMP_PREFIX), 1 << 20)
        cases = {
            "canonical path": (".agents/skills/local-validation-nextjs/SKILL.md", skill, True),
            "relocated folder": (".agents/skills/nextjs-checks/SKILL.md", skill, True),
            "nested folder": (".agents/skills/old/local-validation-nextjs/SKILL.md", skill, True),
            "stamp past 1 MiB": (".agents/skills/big/SKILL.md", late_stamp, True),
            "repository's own folder": (
                ".agents/skills/local-validation-nextjs/SKILL.md",
                "---\nname: local-validation-nextjs\n---\nExample: " + bootstrap.STAMP_PREFIX + "0" * 64 + " -->\n",
                False),
        }
        for label, (rel, content, mismatch) in cases.items():
            with self.subTest(label):
                shutil.rmtree(self.repo / ".agents", ignore_errors=True)
                self._write(rel, content)
                report = bootstrap.compare_repository(self.repo, simple)
                self.assertEqual(bootstrap.TYPE_MISMATCH in report, mismatch, report.get(bootstrap.TYPE_MISMATCH))

    def test_unreadable_other_type_skill_is_not_deleted(self):
        nextjs, simple = _render("nextjs"), _render("simple")
        rel = ".agents/skills/local-validation-nextjs/SKILL.md"
        self._write(rel, nextjs[rel])
        self._commit_all()
        (self.repo / rel).chmod(0)
        try:
            actions = {path: action for action, path, _ in bootstrap.adopt_repository(self.repo, simple)}
        finally:
            (self.repo / rel).chmod(0o644)
        self.assertEqual(actions[rel], "refused")
        self.assertTrue((self.repo / rel).is_file())

    def test_unreachable_skill_target_is_not_dangling(self):
        files = _render()
        self._write(".agents/skills/repo-skill/SKILL.md", "---\nname: repo-skill\n---\n# Ours\n")
        (self.repo / ".claude/skills").mkdir(parents=True)
        (self.repo / ".claude/skills/repo-skill").symlink_to("../../.agents/skills/repo-skill")
        self._commit_all()
        skills = self.repo / ".agents/skills"
        skills.chmod(0)
        try:
            self.assertNotIn(".claude/skills/repo-skill", bootstrap._dangling_mirrors(self.repo, {}))
        finally:
            skills.chmod(0o755)
        self.assertTrue((self.repo / ".claude/skills/repo-skill").is_symlink())

    def test_symlinked_skill_read_does_not_block_on_a_fifo(self):
        files = _render()
        outside = Path(self._tmp.name) / "fifo-skill"
        outside.mkdir()
        os.mkfifo(outside / "SKILL.md")
        (self.repo / ".agents/skills").mkdir(parents=True)
        (self.repo / ".agents/skills/custom").symlink_to(outside)
        done = []
        worker = threading.Thread(target=lambda: done.append(bootstrap.compare_repository(self.repo, files)), daemon=True)
        worker.start()
        worker.join(10)
        self.assertTrue(done, "compare_repository blocked on a FIFO behind a symlinked skill")
        self.assertNotIn(".agents/skills/custom", done[0])

    def test_symlinked_skill_names_survive_crlf_and_a_cut_character(self):
        files = _render()
        cases = {
            "crlf": "---\r\nname: pull-requests\r\n---\r\n# Not the template\r\n",
            "cut multibyte": "---\nname: pull-requests\n---\n" + "\u00e9" * 40,
        }
        (self.repo / ".agents/skills").mkdir(parents=True)
        for label, text in cases.items():
            with self.subTest(label):
                outside = Path(self._tmp.name) / f"skill-{label.replace(' ', '-')}"
                outside.mkdir()
                (outside / "SKILL.md").write_bytes(text.encode())
                link = self.repo / ".agents/skills/custom"
                if link.is_symlink():
                    link.unlink()
                link.symlink_to(outside)
                with unittest.mock.patch.object(bootstrap, "SYMLINKED_SKILL_READ_LIMIT", 33):
                    report = bootstrap.compare_repository(self.repo, files)
                self.assertEqual(report[".agents/skills/custom"][0], "shadowed")

    def test_symlinked_skill_folder_with_a_template_name_is_shadowed(self):
        files = _render()
        outside = Path(self._tmp.name) / "shared-skill"
        outside.mkdir()
        (outside / "SKILL.md").write_text("---\nname: pull-requests\n---\n# Not the template\n")
        (self.repo / ".agents/skills").mkdir(parents=True)
        (self.repo / ".agents/skills/custom").symlink_to(outside)
        report = bootstrap.compare_repository(self.repo, files)
        self.assertEqual(report[".agents/skills/custom"][0], "shadowed")
        self.assertEqual(report[".agents/skills/pull-requests/SKILL.md"][0], "shadowed")
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions[".agents/skills/custom"], "refused")
        self.assertEqual((outside / "SKILL.md").read_text(), "---\nname: pull-requests\n---\n# Not the template\n")

    def test_non_utf8_locale_renders_and_reports_cleanly(self):
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LC_ALL": "en_US.ISO8859-1",
            "LANG": "en_US.ISO8859-1", "PYTHONUTF8": "0", "PYTHONIOENCODING": "",
        }
        root = Path(bootstrap.__file__).resolve().parent
        script = (
            "import bootstrap\n"
            "f = bootstrap.generate_files({'name': 's', 'repo_type': 'simple', 'postgres': False})\n"
            "assert '\\u2014' in f['AGENTS.md'] and '\\u00e2\\u20ac' not in f['AGENTS.md']\n"
        )
        render = subprocess.run([sys.executable, "-c", script], cwd=root, env=env, capture_output=True)
        self.assertEqual(render.returncode, 0, render.stderr.decode(errors="replace"))
        # The --check report prints an em dash on its first line.
        check = subprocess.run(
            [sys.executable, str(root / "bootstrap.py"), "--check", str(self.repo), "--type", "simple"],
            env=env, capture_output=True,
        )
        self.assertIn(check.returncode, (0, 1), check.stderr.decode(errors="replace"))
        self.assertNotIn(b"Traceback", check.stderr)

    def test_adopt_never_writes_through_symlinks(self):
        files = _render()
        outside = Path(self._tmp.name) / "outside.md"
        (self.repo / "README.md").symlink_to(outside)  # dangling
        (self.repo / "docs").symlink_to(Path(self._tmp.name))
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions["README.md"], "refused")
        self.assertEqual(actions["docs/branch-protection-runbook.md"], "refused")
        self.assertFalse(outside.exists())
        self.assertFalse((Path(self._tmp.name) / "branch-protection-runbook.md").exists())

    def test_adopt_refuses_ignored_untracked_agents(self):
        files = _render()
        self._write(".gitignore", "AGENTS.md\n")
        self._commit_all()
        original = files["AGENTS.md"].replace("## Definition of done\n\n", "## Definition of done\n\nX.\n\n", 1)
        self._write("AGENTS.md", original)
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files, True)}
        self.assertEqual(actions["AGENTS.md"], "refused")
        self.assertEqual((self.repo / "AGENTS.md").read_text(), original)

    def test_adopt_refuses_crlf_files(self):
        files = _render()
        crlf = self._agents_missing_a_section(files).replace("\n", "\r\n").encode()
        (self.repo / "AGENTS.md").write_bytes(crlf)
        self._commit_all()
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions["AGENTS.md"], "refused")
        self.assertEqual((self.repo / "AGENTS.md").read_bytes(), crlf)
    def test_check_treats_project_specifics_as_repository_owned(self):
        files = _render()
        self._write("AGENTS.md", files["AGENTS.md"] + "\n- Only ours.\n\n## Local notes\n\nMore.\n")
        status, _ = bootstrap.compare_repository(self.repo, files)["AGENTS.md"]
        self.assertEqual(status, "same")

    def test_ambiguous_structure_is_local(self):
        files = _render()
        generated, owned = bootstrap._split_project_specifics(files["AGENTS.md"])
        setext = generated.replace("## Definition of done\n\n", "## Definition of done\n\nOur rules\n---------\n\n", 1)
        rows = bootstrap.compare_agents(files["AGENTS.md"], setext + owned)
        self.assertIn(("local", "(setext heading: Our rules)"), rows)
        subsection = generated.replace("## Definition of done\n\n", "## Definition of done\n\n### Ours\n\nX.\n\n", 1)
        rows = bootstrap.compare_agents(files["AGENTS.md"], subsection + owned)
        self.assertIn(("local", "## Definition of done › ### Ours"), rows)

    def test_adopt_rewrites_through_a_new_inode(self):
        files = _render()
        outside = Path(self._tmp.name) / "linked-agents"
        outside.write_text(self._agents_missing_a_section(files))
        self._git_init()
        os.link(outside, self.repo / "AGENTS.md")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "init")
        bootstrap.adopt_repository(self.repo, files)
        self.assertEqual(outside.read_text(), self._agents_missing_a_section(files))
        self.assertEqual((self.repo / "AGENTS.md").read_text(), files["AGENTS.md"])
    def test_contained_headings_in_generated_sections_are_local(self):
        files = _render()
        generated, owned = bootstrap._split_project_specifics(files["AGENTS.md"])
        for container in ("> ## Local policy", "- ## Local policy", "1. ### Local policy"):
            edited = generated.replace(
                "## Definition of done\n\n", f"## Definition of done\n\n{container}\n\n", 1
            )
            rows = bootstrap.compare_agents(files["AGENTS.md"], edited + owned)
            self.assertIn(("local", f"## Definition of done › {container}"), rows)

    def test_contained_setext_headings_are_local(self):
        files = _render()
        generated, owned = bootstrap._split_project_specifics(files["AGENTS.md"])
        edited = generated.replace(
            "## Definition of done\n\n",
            "## Definition of done\n\n> Local policy\n> ------------\n>\n> Keep this.\n\n", 1,
        )
        rows = bootstrap.compare_agents(files["AGENTS.md"], edited + owned)
        self.assertIn(("local", "(setext heading: Local policy)"), rows)

    def test_replacement_requires_confirmation_when_a_confirmer_is_given(self):
        files = _render()
        edited = files["AGENTS.md"].replace("## Definition of done\n\n", "## Definition of done\n\nX.\n\n", 1)
        self._write("AGENTS.md", edited)
        self._commit_all()
        seen = []
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(
            self.repo, files, True, confirm=lambda sections: seen.append(sections) or False
        )}
        self.assertEqual(seen, [["## Definition of done"]])
        self.assertEqual(actions["AGENTS.md"], "refused")
        self.assertEqual((self.repo / "AGENTS.md").read_text(), edited)
        bootstrap.adopt_repository(self.repo, files, True, confirm=lambda sections: True)
        self.assertEqual((self.repo / "AGENTS.md").read_text(), files["AGENTS.md"])

    def test_ambiguity_in_repository_owned_text_is_ignored(self):
        files = _render()
        tail = "\nOur heading\n-----------\n\n```\nunclosed\n"
        self._write("AGENTS.md", files["AGENTS.md"] + tail)
        status, _ = bootstrap.compare_repository(self.repo, files)["AGENTS.md"]
        self.assertEqual(status, "same")

    def test_lone_carriage_returns_are_refused(self):
        files = _render()
        self._write("AGENTS.md", self._agents_missing_a_section(files).replace("\n", "\r", 3))
        self._commit_all()
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions["AGENTS.md"], "refused")
    def test_a_per_file_failure_does_not_abort_the_run(self):
        files = _render()
        original = bootstrap._adopt_file

        def flaky(repo_dir, rel, *args):
            if rel == "README.md":
                raise FileExistsError(17, "File exists")
            return original(repo_dir, rel, *args)

        bootstrap._adopt_file = flaky
        try:
            actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        finally:
            bootstrap._adopt_file = original
        self.assertEqual(actions["README.md"], "refused")
        self.assertEqual(actions["AGENTS.md"], "wrote")

    def test_directory_swapped_for_symlink_after_the_scan_is_refused(self):
        files = _render()
        outside = Path(self._tmp.name) / "elsewhere"
        outside.mkdir()
        report = bootstrap.compare_repository(self.repo, files)  # .github does not exist yet
        (self.repo / ".github").symlink_to(outside)
        original = bootstrap.compare_repository
        bootstrap.compare_repository = lambda repo_dir, files: report
        try:
            actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        finally:
            bootstrap.compare_repository = original
        self.assertEqual(actions[".github/workflows/pr-title-check.yml"], "refused")
        self.assertEqual(list(outside.iterdir()), [])
        self.assertEqual(actions["AGENTS.md"], "wrote")

    def test_failed_new_file_leaves_nothing_behind(self):
        files = {"deep/dir/new.txt": "content\n"}
        original = bootstrap._create_anchored

        def failing(parent, name, text, exact_mode=None):
            original(parent, name, text[:2], exact_mode)
            raise OSError(28, "No space left on device")

        bootstrap._create_anchored = failing
        try:
            actions = bootstrap.adopt_repository(self.repo, files)
        finally:
            bootstrap._create_anchored = original
        self.assertEqual(actions[0][0], "refused")
        self.assertEqual(list(self.repo.iterdir()), [])

    def test_rewrite_refused_when_the_file_changes_after_it_was_read(self):
        files = _render()
        self._write("AGENTS.md", self._agents_missing_a_section(files))
        self._commit_all()
        original = bootstrap._create_anchored
        edited = self._agents_missing_a_section(files) + "\nConcurrent edit.\n"

        def edit_then_create(parent, name, text, exact_mode=None):
            (self.repo / "AGENTS.md").write_text(edited)
            original(parent, name, text, exact_mode)

        bootstrap._create_anchored = edit_then_create
        try:
            actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(
                self.repo, {"AGENTS.md": files["AGENTS.md"]}
            )}
        finally:
            bootstrap._create_anchored = original
        self.assertEqual(actions["AGENTS.md"], "refused")
        self.assertEqual((self.repo / "AGENTS.md").read_text(), edited)
        self.assertEqual([p.name for p in self.repo.iterdir() if p.name.endswith(".tmp")], [])
    def test_unreadable_file_is_reported_and_the_run_continues(self):
        files = _render()
        self._write("README.md", "# Mine\n")
        (self.repo / "README.md").chmod(0)
        try:
            status, _ = bootstrap.compare_repository(self.repo, files)["README.md"]
            self.assertEqual(status, "unreadable")
            actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        finally:
            (self.repo / "README.md").chmod(0o644)
        self.assertEqual(actions["README.md"], "refused")
        self.assertEqual(actions["AGENTS.md"], "wrote")

    def test_reordered_generated_sections_are_drift(self):
        files = _render()
        preamble, sections = bootstrap._agents_sections(files["AGENTS.md"])
        titles = [title for title, _ in sections]
        a, b = titles.index("## Branches"), titles.index("## Commits")
        sections[a], sections[b] = sections[b], sections[a]
        swapped = preamble + "".join(body for _, body in sections)
        rows = bootstrap.compare_agents(files["AGENTS.md"], swapped)
        self.assertIn(("differs", "(order of generated sections)"), rows)
        self._write("AGENTS.md", swapped)
        self._commit_all()
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions["AGENTS.md"], "refused")

    def test_longer_fence_hides_inner_fence_and_headings(self):
        text = "## A\n\n````md\n```\n## Project specifics\n```\n````\n\n## B\n"
        _, sections = bootstrap._agents_sections(text)
        self.assertEqual([heading for heading, _ in sections], ["## A", "## B"])
        self.assertEqual(bootstrap._split_project_specifics(text), (text, None))
        self.assertIn("(code fence left open at end of file)", bootstrap._markdown_ambiguities("```\n## A\n"))

    def test_adopt_reports_missing_gitignore_entries_without_writing(self):
        files = _render()
        self._write(".gitignore", "node_modules/\n!.worktrees/keep\n")
        self._commit_all()
        actions = {rel: (action, detail) for action, rel, detail in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions[".gitignore"][0], "kept")
        self.assertIn(".worktrees/", actions[".gitignore"][1])
        self.assertEqual((self.repo / ".gitignore").read_text(), "node_modules/\n!.worktrees/keep\n")

    def test_nextjs_block_is_kept_and_not_compared(self):
        files = _render("nextjs")
        repo_block = (
            "<!-- BEGIN:nextjs-agent-rules -->\n\n# Newer Next.js text\n\n<!-- END:nextjs-agent-rules -->"
        )
        template_block = bootstrap._nextjs_rules_block(files["AGENTS.md"])
        mine = files["AGENTS.md"].replace(template_block, repo_block, 1)
        rows = bootstrap.compare_agents(files["AGENTS.md"], mine)
        self.assertTrue(all(status == "same" for status, _ in rows), rows)
        rebuilt = bootstrap.rebuild_agents(files["AGENTS.md"], mine)
        self.assertIn("# Newer Next.js text", rebuilt)

    def test_headings_inside_code_fences_are_not_sections(self):
        text = "## Tooling\n\n```sh\n# 1. Format check\ncargo fmt\n```\n\n## Next\n"
        _, sections = bootstrap._agents_sections(text)
        self.assertEqual([heading for heading, _ in sections], ["## Tooling", "## Next"])

    def test_claude_md_without_import_is_reported(self):
        files = _render()
        self._write("CLAUDE.md", "Follow AGENTS.md for all project instructions.\n")
        status, detail = bootstrap.compare_repository(self.repo, files)["CLAUDE.md"]
        self.assertEqual(status, "differs")
        self.assertIn("does not import AGENTS.md", detail)

    def test_owned_manifest_and_swift_substitutions(self):
        for repo_type in bootstrap.TEMPLATE_SKILLS:
            cfg = {"name": "sample", "repo_type": repo_type, "postgres": False,
                   "scheme": "My App", "destination": "macos", "xcodegen": True}
            files = bootstrap.generate_files(cfg)
            owned = bootstrap.template_owned_paths(cfg)
            self.assertEqual({path for path, text in files.items() if bootstrap.read_stamp(text)[0]},
                             set(owned))
            self.assertNotIn("docs/lint-baseline.md", owned)
            self.assertNotIn("docs/advisory-baseline.md", owned)
            for path in owned:
                self.assertTrue(bootstrap.stamp_is_valid(files[path]), path)
                self.assertNotRegex(files[path], r"__[A-Z_]+__|# <<[A-Z_]+>>")
            self.assertEqual(bootstrap.generate_links(cfg), bootstrap._links_for_files(files))

    def test_legacy_digest_table_is_reproducible(self):
        with unittest.mock.patch.object(bootstrap, "TEMPLATES_DIR", self._legacy_templates()):
            self.assertEqual(bootstrap.compute_legacy_digests(), bootstrap.LEGACY_TEMPLATE_DIGESTS)

    def test_validator_flags_a_release_missing_from_the_legacy_table(self):
        templates = self._legacy_templates()
        with unittest.mock.patch.object(bootstrap, "TEMPLATES_DIR", templates):
            self.assertEqual(validate_templates.check_legacy_digests(), [])
            runbook = templates / "docs-branch-protection-runbook.md"
            runbook.write_text(runbook.read_text(encoding="utf-8") + "\nA later release.\n", encoding="utf-8")
            _git(templates.parent, "commit", "-q", "-am", "v1.0.0")
            _git(templates.parent, "tag", "v1.0.0")
            # Releases after LEGACY_LAST_TAG ship stamped docs and never join the table.
            self.assertEqual(validate_templates.check_legacy_digests(), [])
            with unittest.mock.patch.object(bootstrap, "LEGACY_LAST_TAG", (1, 0, 0)):
                errors = validate_templates.check_legacy_digests()
        self.assertTrue(any("LEGACY_TEMPLATE_DIGESTS is stale" in error for error in errors), errors)

    def test_legacy_diff_is_skipped_with_a_notice_without_git_or_tags(self):
        files = _render()
        rel = "docs/branch-protection-runbook.md"
        body = _LEGACY_FIXTURES["sources"]["v0.5.5"]["docs-branch-protection-runbook.md"]
        self._write(rel, body + "\nRepository customization.\n")
        self._commit_all()
        copy = Path(self._tmp.name) / "copy" / "templates"
        copy.mkdir(parents=True)
        tagless = Path(self._tmp.name) / "tagless" / "templates"
        tagless.mkdir(parents=True)
        (tagless / "README.md").write_text("untagged\n")
        _git(tagless.parent, "init", "-q")
        _git(tagless.parent, "add", "-A")
        _git(tagless.parent, "commit", "-q", "-m", "untagged")
        for label, templates in (("non-git copy", copy), ("tagless clone", tagless)):
            with self.subTest(label), unittest.mock.patch.object(bootstrap, "TEMPLATES_DIR", templates):
                errors = io.StringIO()
                with contextlib.redirect_stderr(errors):
                    report = bootstrap.compare_repository(self.repo, files)
                self.assertEqual(report[rel], ("local-modified", None))
                self.assertEqual(len(errors.getvalue().splitlines()), 1, errors.getvalue())
                self.assertIn("skipped the diff against legacy template docs", errors.getvalue())

    def test_unstamped_released_runbooks_are_upgraded(self):
        files = _render()
        rel = "docs/branch-protection-runbook.md"
        for ref in ("v0.5.5", "v0.6.0"):
            with self.subTest(ref=ref):
                body = _LEGACY_FIXTURES["sources"][ref]["docs-branch-protection-runbook.md"]
                self._write(rel, body)
                self._commit_all()
                self.assertEqual(bootstrap.compare_repository(self.repo, files)[rel][0], "stale")
                actions = bootstrap.adopt_repository(self.repo, files)
                self.assertEqual(next(a for a in actions if a[1] == rel)[0], "updated")
                self.assertEqual((self.repo / rel).read_text(), files[rel])

    def test_unstamped_current_docs_are_upgraded(self):
        files = _render("nextjs")
        rel = bootstrap.SCREENSHOT_REVIEW
        self._write(rel, bootstrap.read_stamp(files[rel])[1])
        self._commit_all()
        self.assertEqual(bootstrap.compare_repository(self.repo, files)[rel][0], "stale")
        actions = bootstrap.adopt_repository(self.repo, files)
        self.assertEqual(next(a for a in actions if a[1] == rel)[0], "updated")
        self.assertEqual((self.repo / rel).read_text(), files[rel])

    def test_customized_legacy_doc_is_refused_and_diff_is_printed(self):
        files = _render()
        rel = "docs/branch-protection-runbook.md"
        body = _LEGACY_FIXTURES["sources"]["v0.5.5"]["docs-branch-protection-runbook.md"]
        mine = body + "\nRepository customization.\n"
        self._write(rel, mine)
        self._commit_all()
        with unittest.mock.patch.object(bootstrap, "TEMPLATES_DIR", self._legacy_templates()):
            report = bootstrap.compare_repository(self.repo, files)
        self.assertEqual(report[rel][0], "local-modified")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            bootstrap.print_repository_report(self.repo, {"repo_type": "python"}, report)
        self.assertIn(f"--- legacy/{rel}", output.getvalue())
        self.assertIn("+Repository customization.", output.getvalue())
        actions = bootstrap.adopt_repository(self.repo, files)
        self.assertEqual(next(a for a in actions if a[1] == rel)[0], "refused")
        self.assertEqual((self.repo / rel).read_text(), mine)

    def test_stale_skill_is_overwritten_and_then_same(self):
        files = _render()
        rel = ".agents/skills/pull-requests/SKILL.md"
        self._write(rel, bootstrap.stamp("# Older template\n"))
        self._commit_all()
        self.assertEqual(bootstrap.compare_repository(self.repo, files)[rel][0], "stale")
        actions = bootstrap.adopt_repository(self.repo, files)
        self.assertEqual(next(a for a in actions if a[1] == rel)[0], "updated")
        self.assertEqual((self.repo / rel).read_text(), files[rel])
        self.assertEqual(bootstrap.compare_repository(self.repo, files)[rel][0], "same")

    def test_modified_skill_is_refused_even_with_replace_generated(self):
        files = _render()
        rel = ".agents/skills/pull-requests/SKILL.md"
        mine = files[rel] + "\nMy local change.\n"
        self._write(rel, mine)
        self._commit_all()
        self.assertEqual(bootstrap.compare_repository(self.repo, files)[rel][0], "local-modified")
        actions = bootstrap.adopt_repository(self.repo, files, True)
        action = next(a for a in actions if a[1] == rel)
        self.assertEqual(action[0], "refused")
        self.assertIn("repo-owned skill", action[2])
        self.assertEqual((self.repo / rel).read_text(), mine)

    def test_unstamped_template_skill_is_shadowed(self):
        files = _render()
        rel = ".agents/skills/pull-requests/SKILL.md"
        mine = bootstrap.read_stamp(files[rel])[1]
        self._write(rel, mine)
        self._commit_all()
        self.assertEqual(bootstrap.compare_repository(self.repo, files)[rel][0], "shadowed")
        actions = bootstrap.adopt_repository(self.repo, files)
        self.assertEqual(next(a for a in actions if a[1] == rel)[0], "refused")
        self.assertEqual((self.repo / rel).read_text(), mine)

    def test_repo_skill_name_collision_is_shadowed_and_blocks_generation(self):
        files = _render()
        rel = ".agents/skills/mine/SKILL.md"
        self._write(rel, '---\nname: "pull-requests"\ndescription: Local\n---\n\n# Ours\n')
        self._commit_all()
        report = bootstrap.compare_repository(self.repo, files)
        self.assertEqual(report[rel][0], "shadowed")
        actions = bootstrap.adopt_repository(self.repo, files)
        self.assertEqual(next(a for a in actions if a[1] == rel)[0], "refused")
        self.assertFalse((self.repo / ".agents/skills/pull-requests/SKILL.md").exists())

    def test_quoted_frontmatter_names_with_comments_still_shadow_template_skills(self):
        files = _render()
        rel = ".agents/skills/mine/SKILL.md"
        for field in ('name: "pull-requests" # local', "name: 'pull-requests' # local",
                      '"name": pull-requests # local', "'name': pull-requests"):
            with self.subTest(field=field):
                self._write(rel, f"---\n{field}\ndescription: Local\n---\n\n# Ours\n")
                report = bootstrap.compare_repository(self.repo, files)
                self.assertEqual(report[rel][0], "shadowed")

    def test_scalar_names_shadow_and_refuse_both_cli_operations(self):
        files = _render("nextjs")
        bootstrap.adopt_repository(self.repo, files)
        rel = ".agents/skills/mine/SKILL.md"
        for scalar, ambiguous in (
            (">2-\n  pull-requests", True), ("|2-\n  pull-requests", True),
            (">-\n  pull-requests", True), ("|-\n  pull-requests", True),
            ("|\n  pull-requests", True), ('"pull-requests', True),
            ('"pull-requests"', False), ("'pull-requests'", False), ("pull-requests", False),
        ):
            with self.subTest(scalar=scalar):
                self._write(rel, f"---\nname: {scalar}\ndescription: Local\n---\n\n# Ours\n")
                report = bootstrap.compare_repository(self.repo, files)
                self.assertEqual(report[rel][0], "shadowed")
                if ambiguous:
                    self.assertEqual(
                        report[rel][1],
                        "frontmatter name could not be read unambiguously; use a plain single-line name",
                    )
                else:
                    self.assertEqual(report[".agents/skills/pull-requests/SKILL.md"][0], "shadowed")
                original = (self.repo / rel).read_bytes()
                for flag in ("--check", "--adopt"):
                    result = subprocess.run(
                        [sys.executable, "-S", str(Path(bootstrap.__file__)), flag, str(self.repo),
                         "--type", "nextjs"], capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, 1, result.stdout)
                    row = "shadowed" if flag == "--check" else "refused "
                    self.assertIn(f"{row} {rel}", result.stdout)
                    self.assertEqual((self.repo / rel).read_bytes(), original)

    def test_ambiguous_names_are_refused_even_without_a_known_collision(self):
        files = _render()
        rel = ".agents/skills/mine/SKILL.md"
        for field in ("name: >2-\n  unique-local-skill", "name: [unique-local-skill]",
                      "name: mine\nname: other",
                      'name: mine\n"na\\u006de": pull-requests'):
            with self.subTest(field=field):
                self._write(rel, f"---\n{field}\ndescription: Local\n---\n\n# Ours\n")
                report = bootstrap.compare_repository(self.repo, files)
                self.assertEqual(
                    report[rel],
                    ("shadowed", "frontmatter name could not be read unambiguously; use a plain single-line name"),
                )
                actions = bootstrap.adopt_repository(self.repo, files)
                self.assertEqual(next(a for a in actions if a[1] == rel)[0], "refused")

    def test_non_utf8_repo_skill_name_cannot_report_alignment(self):
        files = _render()
        rel = ".agents/skills/mine/SKILL.md"
        path = self.repo / rel
        path.parent.mkdir(parents=True)
        original = b"---\nname: \xff\n---\n"
        path.write_bytes(original)
        report = bootstrap.compare_repository(self.repo, files)
        self.assertEqual(
            report[rel],
            ("shadowed", "frontmatter name could not be read unambiguously; use a plain single-line name"),
        )
        actions = bootstrap.adopt_repository(self.repo, files)
        self.assertEqual(next(a for a in actions if a[1] == rel)[0], "refused")
        self.assertEqual(path.read_bytes(), original)

    def test_stamped_ambiguous_frontmatter_cannot_be_deleted_as_an_orphan(self):
        files = _render()
        bootstrap.adopt_repository(self.repo, files)
        rel = ".agents/skills/mine/SKILL.md"
        for opening in ("\ufeff---\n", "---\r\n"):
            with self.subTest(opening=opening):
                text = bootstrap.stamp(
                    opening + "name: >2-\n  unique-local-skill\ndescription: Local\n---\n\n# Ours\n"
                )
                self.assertTrue(bootstrap.stamp_is_valid(text))
                self._write(rel, text)
                original = (self.repo / rel).read_bytes()
                report = bootstrap.compare_repository(self.repo, files)
                self.assertEqual(
                    report[rel],
                    ("shadowed", "frontmatter name could not be read unambiguously; use a plain single-line name"),
                )
                for flag in ("--check", "--adopt"):
                    result = subprocess.run(
                        [sys.executable, "-S", str(Path(bootstrap.__file__)), flag, str(self.repo),
                         "--type", "python"], capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, 1, result.stdout)
                    self.assertEqual((self.repo / rel).read_bytes(), original)

    def test_ignored_owned_paths_are_not_written(self):
        files = _render()
        rel = ".agents/skills/pull-requests/SKILL.md"
        self._write(".gitignore", ".agents/\n.opencode/\n.claude/skills/\n")
        self._commit_all()
        report = bootstrap.compare_repository(self.repo, files)
        self.assertEqual(report[rel][0], "ignored")
        self.assertEqual(report[".opencode/agents/fresh-eyes-reviewer.md"][0], "ignored")
        actions = bootstrap.adopt_repository(self.repo, files)
        self.assertEqual(next(a for a in actions if a[1] == rel)[0], "refused")
        self.assertFalse((self.repo / rel).exists())
        self.assertFalse((self.repo / ".claude/skills/pull-requests").exists())

    def test_ignore_checks_scrub_inherited_repository_context(self):
        files = _render()
        self._write(".gitignore", ".agents/\n")
        self._commit_all()
        other = Path(self._tmp.name) / "other"
        other.mkdir()
        _git(other, "init", "-q")
        overrides = {"GIT_DIR": str(other / ".git"), "GIT_WORK_TREE": str(other)}
        with unittest.mock.patch.dict(os.environ, overrides):
            report = bootstrap.compare_repository(self.repo, files)
        self.assertEqual(report[".agents/skills/pull-requests/SKILL.md"][0], "ignored")

    def test_ignore_negations_allow_generated_content_only(self):
        files = _render()
        self._write(".gitignore", files[".gitignore"])
        self._git_init()
        for rel in bootstrap.template_owned_paths({"repo_type": "python"}):
            self.assertFalse(bootstrap._git_ignored(self.repo, rel), rel)
        for rel in (".agents/cache/state", ".opencode/state", ".claude/worktrees/work"):
            self.assertTrue(bootstrap._git_ignored(self.repo, rel), rel)

    def test_unmodified_orphans_are_deleted_but_modified_orphans_are_refused(self):
        files = _render()
        for base in (".agents/skills/old", ".claude/agents", ".opencode/agents"):
            rel = f"{base}/SKILL.md" if base.startswith(".agents") else f"{base}/old.md"
            self._write(rel, bootstrap.stamp("# Old\n"))
        modified = ".agents/skills/edited/SKILL.md"
        mine = bootstrap.stamp("# Old\n") + "Local edit.\n"
        self._write(modified, mine)
        self._commit_all()
        report = bootstrap.compare_repository(self.repo, files)
        orphans = {rel for rel, (status, _) in report.items() if status == "orphaned"}
        self.assertEqual(len(orphans), 4)
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        for rel in orphans - {modified}:
            self.assertEqual(actions[rel], "deleted")
            self.assertFalse((self.repo / rel).exists())
        self.assertEqual(actions[modified], "refused")
        self.assertEqual((self.repo / modified).read_text(), mine)

    def test_unstamped_repo_skills_are_not_orphans(self):
        files = _render()
        rel = ".agents/skills/mine/SKILL.md"
        self._write(rel, "---\nname: mine\n---\n\n# Mine\n")
        self.assertNotIn(rel, bootstrap.compare_repository(self.repo, files))

    def test_retired_sections_need_opt_in_then_are_dropped(self):
        files = _render()
        title = "## Pull requests (squash-merge + Release Please)"
        retired = title + "\n\n### Standard pull requests\n\nOld policy.\n\n"
        mine = retired + files["AGENTS.md"] + "\nLocal specifics.\n"
        self._write("AGENTS.md", mine)
        self._commit_all()
        rows = bootstrap.compare_agents(files["AGENTS.md"], mine)
        self.assertIn(("retired", title), rows)
        self.assertNotIn(("local", title), rows)
        actions = bootstrap.adopt_repository(self.repo, files)
        self.assertEqual(next(a for a in actions if a[1] == "AGENTS.md")[0], "refused")
        self.assertEqual((self.repo / "AGENTS.md").read_text(), mine)
        actions = bootstrap.adopt_repository(self.repo, files, True)
        self.assertEqual(next(a for a in actions if a[1] == "AGENTS.md")[0], "updated")
        self.assertEqual((self.repo / "AGENTS.md").read_text(), files["AGENTS.md"] + "\nLocal specifics.\n")

    def test_retired_section_text_is_shown_by_check_and_dropped_on_replace(self):
        files = _render()
        title = "## Worktrees, verification copies, and scratch output"
        rule = "LOCAL RULE: never use /tmp here."
        mine = title + "\n\n" + rule + "\n\n" + files["AGENTS.md"]
        self._write("AGENTS.md", mine)
        self._commit_all()
        status, rows = bootstrap.compare_repository(self.repo, files)["AGENTS.md"]
        self.assertIn(("retired", title), rows)
        self.assertFalse([heading for row_status, heading in rows if row_status == "local"], rows)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            bootstrap.print_repository_report(self.repo, {"repo_type": "python"}, {"AGENTS.md": (status, rows)})
        self.assertIn("notice: retired section contains 1 line of text", output.getvalue())
        self.assertIn(f"          {rule}\n", output.getvalue())
        actions = bootstrap.adopt_repository(self.repo, files, True)
        self.assertEqual(next(a for a in actions if a[1] == "AGENTS.md")[0], "updated")
        self.assertNotIn(rule, (self.repo / "AGENTS.md").read_text())

    def test_real_v055_nextjs_migration_preserves_project_specifics(self):
        self._migrate_real_v055_agents("nextjs")

    def test_real_v055_swift_migration_preserves_project_specifics(self):
        self._migrate_real_v055_agents("swift")

    def test_real_v055_nextjs_without_retired_section_still_migrates(self):
        self._migrate_real_v055_agents("nextjs", omit_retired=True)

    def test_real_v055_swift_without_retired_section_still_migrates(self):
        self._migrate_real_v055_agents("swift", omit_retired=True)

    def test_type_specific_retired_headings_remain_local_in_other_types(self):
        files = _render("python")
        for heading in ("## Local browser-validation constraints", "## Formatting",
                        "## Baseline process"):
            with self.subTest(heading=heading):
                actual = heading + "\n\nRepository policy.\n\n" + files["AGENTS.md"]
                self.assertIn(("local", heading), bootstrap.compare_agents(files["AGENTS.md"], actual))

    def _migrate_real_v055_agents(self, repo_type, omit_retired=False):
        cfg = {"name": "sample", "repo_type": repo_type, "postgres": False,
               "scheme": "My App", "destination": "iphone", "xcodegen": True}
        files = bootstrap.generate_files(cfg)
        original = _LEGACY_FIXTURES["agents"][repo_type]
        retired_title = ("## Local browser-validation constraints" if repo_type == "nextjs"
                         else "## Formatting")
        if omit_retired:
            preamble, sections = bootstrap._agents_sections(original)
            original = preamble + "".join(body for heading, body in sections if heading != retired_title)
        self._write("AGENTS.md", original)
        self._commit_all()
        owned = bootstrap._split_project_specifics(original)[1].encode("utf-8")
        rows = bootstrap.compare_agents(files["AGENTS.md"], original)
        self.assertFalse([heading for status, heading in rows if status == "local"], rows)
        if omit_retired:
            self.assertNotIn(("retired", retired_title), rows)
        else:
            self.assertIn(("retired", retired_title), rows)
        actions = bootstrap.adopt_repository(self.repo, files, True)
        self.assertNotIn("refused", {action for action, _, _ in actions}, actions)
        self.assertEqual(next(a for a in actions if a[1] == "AGENTS.md")[0], "updated")
        result = (self.repo / "AGENTS.md").read_bytes()
        self.assertTrue(result.endswith(owned))
        self.assertEqual(bootstrap._split_project_specifics(result.decode("utf-8"))[1].encode("utf-8"),
                         owned)
        self.assertEqual(bootstrap.compare_repository(self.repo, files)["AGENTS.md"][0], "same")

    def test_replace_generated_accepts_agents_without_final_newline(self):
        files = _render("simple")
        original = files["AGENTS.md"].replace(
            "## Definition of done\n", "## Definition of done\n\nOlder generated text.\n", 1
        ).rstrip("\n")
        self._write("AGENTS.md", original)
        self._commit_all()
        owned = bootstrap._split_project_specifics(original)[1]
        actions = bootstrap.adopt_repository(self.repo, files, True)
        self.assertEqual(next(a for a in actions if a[1] == "AGENTS.md")[0], "updated")
        generated = bootstrap._split_project_specifics(files["AGENTS.md"])[0]
        self.assertEqual((self.repo / "AGENTS.md").read_text(), generated + owned)

    def test_unknown_subheading_in_retired_section_is_refused(self):
        files = _render()
        title = "## Worktrees, verification copies, and scratch output"
        mine = title + "\n\n### Local policy\n\nKeep.\n\n" + files["AGENTS.md"]
        self._write("AGENTS.md", mine)
        self._commit_all()
        actions = bootstrap.adopt_repository(self.repo, files, True)
        action = next(a for a in actions if a[1] == "AGENTS.md")
        self.assertEqual(action[0], "refused")
        self.assertIn("### Local policy", action[2])
        self.assertEqual((self.repo / "AGENTS.md").read_text(), mine)
        with self.assertRaisesRegex(ValueError, "Local policy"):
            bootstrap.rebuild_agents(files["AGENTS.md"], mine, True)

    def test_mirrors_are_created_relative_and_report_same(self):
        files = _render()
        bootstrap.adopt_repository(self.repo, files)
        for rel, target in bootstrap.generate_links({"repo_type": "python"}).items():
            self.assertEqual(os.readlink(self.repo / rel), target)
            self.assertEqual((self.repo / rel / "SKILL.md").read_text(),
                             files[f".agents/skills/{Path(rel).name}/SKILL.md"])
            self.assertEqual(bootstrap.compare_repository(self.repo, files)[rel][0], "same")

    def test_wrong_mirror_targets_and_regular_files_are_refused(self):
        files = _render()
        regular = ".claude/skills/pull-requests"
        wrong = ".claude/skills/delegation"
        self._write(regular, "Keep me.\n")
        (self.repo / wrong).symlink_to("../../outside")
        report = bootstrap.compare_repository(self.repo, files)
        self.assertEqual(report[regular][0], "differs")
        self.assertEqual(report[wrong][0], "differs")
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions[regular], "refused")
        self.assertEqual(actions[wrong], "refused")
        self.assertEqual((self.repo / regular).read_text(), "Keep me.\n")
        self.assertEqual(os.readlink(self.repo / wrong), "../../outside")

    def test_mirror_parent_symlink_is_refused(self):
        files = _render()
        outside = Path(self._tmp.name) / "outside"
        outside.mkdir()
        (self.repo / ".claude").mkdir()
        (self.repo / ".claude/skills").symlink_to(outside)
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions[".claude/skills/pull-requests"], "refused")
        self.assertEqual(list(outside.iterdir()), [])

    def test_stale_owned_file_requires_tracked_clean_lf_utf8(self):
        files = _render()
        rel = "docs/branch-protection-runbook.md"
        variants = [
            bootstrap.stamp("# Old\r\n").encode(),
            bootstrap.stamp("# Old").encode(),
            bootstrap.stamp("# Old\n").encode() + b"\xff\n",
        ]
        for raw in variants:
            with self.subTest(raw=raw):
                path = self.repo / rel
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(raw)
                self._commit_all()
                actions = bootstrap.adopt_repository(self.repo, files)
                self.assertEqual(next(a for a in actions if a[1] == rel)[0], "refused")
                self.assertEqual(path.read_bytes(), raw)
        self._write(rel, bootstrap.stamp("# Uncommitted\n"))
        actions = bootstrap.adopt_repository(self.repo, files)
        self.assertEqual(next(a for a in actions if a[1] == rel)[0], "refused")
        (self.repo / rel).unlink()
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "delete")
        self._write(rel, bootstrap.stamp("# Untracked\n"))
        actions = bootstrap.adopt_repository(self.repo, files)
        self.assertEqual(next(a for a in actions if a[1] == rel)[0], "refused")

    def test_stale_scan_does_not_overwrite_a_new_local_edit(self):
        files = _render()
        rel = "docs/branch-protection-runbook.md"
        self._write(rel, bootstrap.stamp("# Old\n"))
        self._commit_all()
        report = bootstrap.compare_repository(self.repo, files)
        mine = (self.repo / rel).read_text() + "Changed after scan.\n"
        self._write(rel, mine)
        self._commit_all()
        with unittest.mock.patch.object(bootstrap, "compare_repository", return_value=report):
            actions = bootstrap.adopt_repository(self.repo, files)
        self.assertEqual(next(a for a in actions if a[1] == rel)[0], "refused")
        self.assertEqual((self.repo / rel).read_text(), mine)

    def test_stale_rewrite_refuses_a_concurrent_edit_after_anchored_read(self):
        files = _render()
        rel = "docs/branch-protection-runbook.md"
        old = bootstrap.stamp("# Old\n")
        self._write(rel, old)
        self._commit_all()
        create = bootstrap._create_anchored
        mine = old + "Concurrent edit.\n"

        def edit_then_create(parent, name, text, exact_mode=None):
            (self.repo / rel).write_text(mine)
            create(parent, name, text, exact_mode)

        with unittest.mock.patch.object(bootstrap, "_create_anchored", edit_then_create):
            actions = bootstrap.adopt_repository(self.repo, {rel: files[rel]})
        self.assertEqual(actions[0][0], "refused")
        self.assertEqual((self.repo / rel).read_text(), mine)
        self.assertEqual(list((self.repo / "docs").glob("*.tmp")), [])

    def test_modified_orphan_after_scan_is_not_deleted(self):
        files = _render()
        rel = ".agents/skills/old/SKILL.md"
        old = bootstrap.stamp("# Old\n")
        self._write(rel, old)
        self._commit_all()
        report = bootstrap.compare_repository(self.repo, files)
        mine = old + "Concurrent edit.\n"
        self._write(rel, mine)
        with unittest.mock.patch.object(bootstrap, "compare_repository", return_value=report):
            actions = bootstrap.adopt_repository(self.repo, files)
        self.assertEqual(next(a for a in actions if a[1] == rel)[0], "refused")
        self.assertEqual((self.repo / rel).read_text(), mine)

    def test_index_flags_that_hide_edits_count_as_uncommitted(self):
        files = _render()
        original = self._agents_missing_a_section(files)
        edited = original.replace("## Branches\n\n", "## Branches\n\nUncommitted local rule.\n\n", 1)
        self.assertNotEqual(edited, original)
        for flag in ("--skip-worktree", "--assume-unchanged"):
            with self.subTest(flag=flag):
                self.repo = Path(self._tmp.name) / flag.strip("-")
                self.repo.mkdir()
                self._write("AGENTS.md", original)
                self._commit_all()
                _git(self.repo, "update-index", flag, "AGENTS.md")
                self._write("AGENTS.md", edited)
                actions = {
                    rel: action
                    for action, rel, _ in bootstrap.adopt_repository(
                        self.repo, files, True, confirm=lambda sections: True
                    )
                }
                self.assertEqual(actions["AGENTS.md"], "refused")
                self.assertEqual((self.repo / "AGENTS.md").read_text(), edited)

    def test_orphan_with_a_staged_edit_is_not_deleted(self):
        files = _render()
        rel = ".claude/agents/retired.md"
        old = bootstrap.stamp("# Retired\n")
        self._write(rel, old)
        self._commit_all()
        self._write(rel, "# Local edit staged in the index\n")
        _git(self.repo, "add", rel)
        self._write(rel, old)
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions[rel], "refused")
        self.assertEqual((self.repo / rel).read_text(), old)

    def test_orphan_with_a_staged_removal_is_not_deleted(self):
        files = _render()
        rel = ".claude/agents/retired.md"
        old = bootstrap.stamp("# Retired\n")
        self._write(rel, old)
        self._commit_all()
        _git(self.repo, "rm", "-q", "--cached", rel)
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions[rel], "refused")
        self.assertEqual((self.repo / rel).read_text(), old)

    def test_hidden_edit_is_found_for_a_name_that_looks_like_a_pathspec(self):
        files = _render()
        rel = ".claude/agents/x*.md"
        self._write(rel, bootstrap.stamp("# Retired\n"))
        self._write(".claude/agents/x!.md", "Repository-owned agent.\n")
        self._commit_all()
        _git(self.repo, "update-index", "--skip-worktree", rel)
        hidden = bootstrap.stamp("# Retired, edited locally\n")
        self._write(rel, hidden)
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions[rel], "refused")
        self.assertEqual((self.repo / rel).read_text(), hidden)

    def test_wildcard_orphan_is_judged_without_its_dirty_sibling(self):
        files = _render()
        rel = ".claude/agents/x*.md"
        sibling = ".claude/agents/x!.md"
        self._write(rel, bootstrap.stamp("# Retired\n"))
        self._write(sibling, "Repository-owned agent.\n")
        self._commit_all()
        self._write(sibling, "Repository-owned agent, edited.\n")
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions[rel], "deleted")
        self.assertEqual((self.repo / sibling).read_text(), "Repository-owned agent, edited.\n")

    def test_orphan_is_not_deleted_when_git_cannot_read_the_repository(self):
        files = _render()
        rel = ".claude/agents/retired.md"
        old = bootstrap.stamp("# Retired\n")
        self._write(rel, old)
        self._commit_all()
        self._write(rel, "# Local edit staged in the index\n")
        _git(self.repo, "add", rel)
        self._write(rel, old)
        # Git's ownership check refuses the repository; isolate it from any
        # safe.directory the machine's own config might set.
        refused_by_git = {
            "GIT_TEST_ASSUME_DIFFERENT_OWNER": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        with unittest.mock.patch.dict(os.environ, refused_by_git):
            probe = subprocess.run(["git", "-C", str(self.repo), "status"], capture_output=True)
            self.assertNotEqual(probe.returncode, 0, "git did not apply its ownership check")
            actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions[rel], "refused")
        self.assertEqual((self.repo / rel).read_text(), old)

    def test_git_state_is_unknown_when_git_cannot_run(self):
        self._git_init()
        outside = Path(self._tmp.name) / "not-a-repo"
        outside.mkdir()
        with unittest.mock.patch.object(bootstrap.subprocess, "run", side_effect=FileNotFoundError("git")):
            self.assertEqual(bootstrap._git_file_state(self.repo, "README.md"), "dirty")
            self.assertEqual(bootstrap._git_file_state(outside, "README.md"), "untracked")

    def test_case_differing_hard_links_are_separate_entries(self):
        (self.repo / "case-probe").write_text("")
        if (self.repo / "CASE-PROBE").exists():
            self.skipTest("needs a case-sensitive filesystem")
        (self.repo / "case-probe").unlink()
        files = _render()
        canonical = ".claude/agents/fresh-eyes-reviewer.md"
        twin = ".claude/agents/FRESH-EYES-REVIEWER.md"
        self._write(canonical, files[canonical])
        os.link(self.repo / canonical, self.repo / twin)
        self._commit_all()
        self.assertEqual(bootstrap.compare_repository(self.repo, files)[twin][0], "orphaned")
        actions = {rel: action for action, rel, _ in bootstrap.adopt_repository(self.repo, files)}
        self.assertEqual(actions[twin], "deleted")
        self.assertEqual((self.repo / canonical).read_text(), files[canonical])

    def test_case_only_rename_of_a_live_file_is_not_deleted(self):
        (self.repo / "case-probe").write_text("")
        if not (self.repo / "CASE-PROBE").exists():
            self.skipTest("needs a case-insensitive filesystem")
        (self.repo / "case-probe").unlink()
        files = _render()
        renames = {
            ".claude/agents/fresh-eyes-reviewer.md": ".claude/agents/FRESH-EYES-REVIEWER.md",
            ".agents/skills/pull-requests/SKILL.md": ".agents/skills/pull-requests/skill.md",
        }
        for canonical in renames:
            self._write(canonical, files[canonical])
        self._commit_all()
        for canonical, alias in renames.items():
            _git(self.repo, "mv", canonical, alias)
        _git(self.repo, "commit", "-q", "-m", "rename by case")
        # A directory renamed by case aliases every file below it.
        skill = ".agents/skills/worktrees-and-scratch/SKILL.md"
        self._write(skill, files[skill])
        self._commit_all()
        os.rename(self.repo / Path(skill).parent, self.repo / ".agents/skills/Worktrees-And-Scratch")
        renames[skill] = ".agents/skills/Worktrees-And-Scratch/SKILL.md"
        report = bootstrap.compare_repository(self.repo, files)
        actions = {rel: (action, detail) for action, rel, detail in bootstrap.adopt_repository(self.repo, files)}
        for canonical, alias in renames.items():
            with self.subTest(alias=alias):
                self.assertEqual(report[alias][0], "shadowed")
                self.assertEqual(actions[alias][0], "refused")
                self.assertIn(canonical, actions[alias][1])
                self.assertEqual((self.repo / canonical).read_text(), files[canonical])

    def test_ignored_orphan_is_refused_and_not_deleted(self):
        files = _render()
        rel = ".agents/skills/old/SKILL.md"
        old = bootstrap.stamp("# Old\n")
        self._write(rel, old)
        self._write(".gitignore", ".agents/skills/old/\n")
        self._commit_all()
        self.assertEqual(bootstrap.compare_repository(self.repo, files)[rel][0], "ignored")
        actions = bootstrap.adopt_repository(self.repo, files)
        self.assertEqual(next(a for a in actions if a[1] == rel)[0], "refused")
        self.assertEqual((self.repo / rel).read_text(), old)

    def test_orphan_ignore_rule_added_after_scan_prevents_deletion(self):
        files = _render()
        rel = ".agents/skills/old/SKILL.md"
        old = bootstrap.stamp("# Old\n")
        self._write(rel, old)
        self._git_init()
        report = bootstrap.compare_repository(self.repo, files)
        self.assertEqual(report[rel][0], "orphaned")
        self._write(".gitignore", ".agents/skills/old/\n")
        with unittest.mock.patch.object(bootstrap, "compare_repository", return_value=report):
            actions = bootstrap.adopt_repository(self.repo, files)
        self.assertEqual(next(a for a in actions if a[1] == rel)[0], "refused")
        self.assertEqual((self.repo / rel).read_text(), old)

    def test_duplicate_stamped_orphan_is_refused_instead_of_hidden(self):
        files = _render()
        rel = ".agents/skills/old/SKILL.md"
        old = bootstrap.stamp("# Old\n")
        mine = old.splitlines(keepends=True)[0] + old
        self._write(rel, mine)
        self._commit_all()
        self.assertEqual(bootstrap.compare_repository(self.repo, files)[rel][0], "orphaned")
        actions = bootstrap.adopt_repository(self.repo, files)
        self.assertEqual(next(a for a in actions if a[1] == rel)[0], "refused")
        self.assertEqual((self.repo / rel).read_text(), mine)

    def test_missing_mirror_created_after_scan_is_never_replaced(self):
        files = _render()
        rel = ".claude/skills/pull-requests"
        report = bootstrap.compare_repository(self.repo, files)
        self._write(rel, "Created after scan.\n")
        with unittest.mock.patch.object(bootstrap, "compare_repository", return_value=report):
            actions = bootstrap.adopt_repository(self.repo, files)
        self.assertEqual(next(a for a in actions if a[1] == rel)[0], "refused")
        self.assertEqual((self.repo / rel).read_text(), "Created after scan.\n")

    def test_declared_mirror_exemption_never_applies_to_ancestor_components(self):
        files = _render()
        bootstrap.adopt_repository(self.repo, files)
        links = bootstrap._links_for_files(files)
        rel = ".claude/skills/pull-requests"
        self.assertFalse(bootstrap._symlink_in_path(self.repo, rel, links))
        self.assertTrue(bootstrap._symlink_in_path(self.repo, rel + "/SKILL.md", links))

    def test_missing_skill_parent_swapped_after_scan_is_refused(self):
        files = _render()
        rel = ".agents/skills/pull-requests/SKILL.md"
        report = bootstrap.compare_repository(self.repo, files)
        outside = Path(self._tmp.name) / "outside"
        outside.mkdir()
        (self.repo / ".agents").symlink_to(outside)
        with unittest.mock.patch.object(bootstrap, "compare_repository", return_value=report):
            actions = bootstrap.adopt_repository(self.repo, files)
        self.assertEqual(next(a for a in actions if a[1] == rel)[0], "refused")
        self.assertEqual(list(outside.iterdir()), [])

    def test_new_ignore_rule_after_scan_prevents_missing_skill_creation(self):
        files = _render()
        rel = ".agents/skills/pull-requests/SKILL.md"
        self._git_init()
        report = bootstrap.compare_repository(self.repo, files)
        self._write(".gitignore", ".agents/\n")
        with unittest.mock.patch.object(bootstrap, "compare_repository", return_value=report):
            actions = bootstrap.adopt_repository(self.repo, files)
        self.assertEqual(next(a for a in actions if a[1] == rel)[0], "refused")
        self.assertFalse((self.repo / rel).exists())

    def test_staged_owned_changes_are_not_overwritten(self):
        files = _render()
        rel = "docs/branch-protection-runbook.md"
        self._write(rel, bootstrap.stamp("# Old\n"))
        self._commit_all()
        mine = bootstrap.stamp("# Staged\n")
        self._write(rel, mine)
        _git(self.repo, "add", "--", rel)
        actions = bootstrap.adopt_repository(self.repo, files)
        self.assertEqual(next(a for a in actions if a[1] == rel)[0], "refused")
        self.assertEqual((self.repo / rel).read_text(), mine)

    def test_large_agents_warns_without_changing_alignment(self):
        files = _render()
        bootstrap.adopt_repository(self.repo, files)
        self._write("AGENTS.md", files["AGENTS.md"] + "\n" + "x" * 20_000 + "\n")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            aligned = bootstrap.print_repository_report(
                self.repo, {"repo_type": "python"}, bootstrap.compare_repository(self.repo, files)
            )
        size = (self.repo / "AGENTS.md").stat().st_size
        self.assertIn(f"warn AGENTS.md total {size} B > 20000 B", output.getvalue())
        self.assertTrue(aligned)
        result = subprocess.run(
            [sys.executable, str(Path(bootstrap.__file__)), "--check", str(self.repo), "--type", "python"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_create_and_push_materializes_all_declared_mirrors(self):
        files = _render()
        cfg = {"name": "sample", "repo_type": "python", "owner": "owner",
               "private": True, "repo_dir": self.repo}
        calls = []

        def run(command, **kwargs):
            calls.append(command)

        with unittest.mock.patch.object(bootstrap, "_run", run):
            bootstrap.create_and_push(cfg, files)
        for rel, target in bootstrap.generate_links(cfg).items():
            self.assertTrue((self.repo / rel).is_symlink())
            self.assertEqual(os.readlink(self.repo / rel), target)
        self.assertTrue(cfg["files_pushed"])
        self.assertEqual(calls[-1][:4], ["git", "-C", str(self.repo), "push"])

    def test_create_and_push_refuses_before_creating_without_anchored_symlinks(self):
        files = _render()
        cfg = {"name": "sample", "repo_type": "python", "owner": "owner",
               "private": True, "repo_dir": self.repo}
        calls = []
        stderr = io.StringIO()
        with unittest.mock.patch.object(bootstrap, "_run", lambda command, **kwargs: calls.append(command)), \
                unittest.mock.patch.object(bootstrap, "_ANCHORED_WRITES", False), \
                contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit):
            bootstrap.create_and_push(cfg, files)
        self.assertIn("cannot create anchored symlinks", stderr.getvalue())
        self.assertEqual(calls, [])
        self.assertNotIn("repo_created", cfg)
        self.assertEqual(list(self.repo.iterdir()), [])

    def test_dry_run_prints_links_without_writing(self):
        files = _render()
        cfg = {"name": "sample", "repo_type": "python", "owner": "owner",
               "private": True, "repo_dir": self.repo}
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            bootstrap.print_dry_run(cfg, files)
        for rel, target in bootstrap.generate_links(cfg).items():
            self.assertIn(f"{rel} -> {target}", output.getvalue())
        self.assertEqual(list(self.repo.iterdir()), [])


class StampTests(unittest.TestCase):
    def test_stamp_roundtrips_exact_bodies_including_malformed_line_endings(self):
        bodies = [
            "# Body\n", "# Body", "# CRLF\r\n",
            "---\nname: skill\n---\n\n# Body\n",
            "---\nname: skill\n---\n", "---\n",
        ]
        for body in bodies:
            with self.subTest(body=body):
                stamped = bootstrap.stamp(body)
                self.assertTrue(bootstrap.stamp_is_valid(stamped))
                self.assertEqual(bootstrap.read_stamp(stamped)[1], body)
                self.assertEqual(bootstrap.stamp(stamped), stamped)
                if body.startswith("---\n") and "\n---\n" in body:
                    self.assertIn("\n---\n" + bootstrap.STAMP_PREFIX, stamped)
                else:
                    self.assertTrue(stamped.startswith(bootstrap.STAMP_PREFIX))

    def test_frontmatter_only_without_newline_gets_a_valid_separated_stamp(self):
        stamped = bootstrap.stamp("---\nname: skill\n---")
        self.assertIn("\n---\n" + bootstrap.STAMP_PREFIX, stamped)
        self.assertTrue(bootstrap.stamp_is_valid(stamped))

    def test_stamp_follows_bom_and_crlf_frontmatter(self):
        cases = {
            "BOM+LF": ("\ufeff---\nname: skill\n---\n", "\n# Body\n"),
            "CRLF": ("---\r\nname: skill\r\n---\r\n", "\r\n# Body\r\n"),
            "BOM+CRLF": ("\ufeff---\r\nname: skill\r\n---\r\n", "\r\n# Body\r\n"),
        }
        for label, (frontmatter, rest) in cases.items():
            with self.subTest(label):
                body = frontmatter + rest
                eol = frontmatter[-2:] if frontmatter.endswith("\r\n") else "\n"
                stamped = bootstrap.stamp(body)
                marker = stamped[len(frontmatter):].split(eol, 1)[0]
                self.assertTrue(stamped.startswith(frontmatter + bootstrap.STAMP_PREFIX))
                self.assertEqual(stamped, frontmatter + marker + eol + rest)
                self.assertTrue(bootstrap.stamp_is_valid(stamped))
                self.assertEqual(bootstrap.read_stamp(stamped)[1], body)
                self.assertEqual(bootstrap.stamp(stamped), stamped)

    def test_crlf_frontmatter_only_without_newline_gets_a_crlf_separated_stamp(self):
        stamped = bootstrap.stamp("\ufeff---\r\nname: skill\r\n---")
        self.assertTrue(stamped.startswith("\ufeff---\r\nname: skill\r\n---\r\n" + bootstrap.STAMP_PREFIX))
        self.assertTrue(stamped.endswith(" -->\r\n"))
        self.assertTrue(bootstrap.stamp_is_valid(stamped))

    def test_invalid_duplicate_and_modified_stamps_do_not_validate(self):
        valid = bootstrap.stamp("# Body\n")
        marker = valid.splitlines(keepends=True)[0]
        for text in ("# No stamp\n", valid + "Local\n", marker + valid,
                     valid.replace("sha256=", "sha256=invalid")):
            with self.subTest(text=text):
                self.assertFalse(bootstrap.stamp_is_valid(text))


class RepositoryNameTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.repo = self.root / "sample"
        self.repo.mkdir()
        (self.repo / "README.md").write_text("sample\n")
        _git(self.repo, "init", "-q")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "init")

    def tearDown(self):
        self._tmp.cleanup()

    def test_main_checkout_uses_its_directory_name(self):
        self.assertEqual(bootstrap.existing_repository_name(self.repo), "sample")

    def test_linked_worktree_uses_the_main_checkout_name(self):
        worktree = self.root / ".worktrees" / "sample" / "align"
        _git(self.repo, "worktree", "add", "-q", "--detach", str(worktree))
        self.assertEqual(bootstrap.existing_repository_name(worktree), "sample")

    def test_inherited_git_dir_does_not_name_another_repository(self):
        other = self.root / "other"
        other.mkdir()
        _git(other, "init", "-q")
        overrides = {"GIT_DIR": str(other / ".git"), "GIT_WORK_TREE": str(other)}
        with unittest.mock.patch.dict(os.environ, overrides):
            self.assertEqual(bootstrap.existing_repository_name(self.repo), "sample")

    def test_command_scope_git_config_is_kept(self):
        config = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "safe.directory",
                  "GIT_CONFIG_VALUE_0": "*"}
        seen = {}
        real_run = subprocess.run

        def spy(*args, **kwargs):
            seen.update(kwargs.get("env") or {})
            return real_run(*args, **kwargs)

        with unittest.mock.patch.dict(os.environ, config), \
                unittest.mock.patch.object(bootstrap.subprocess, "run", spy):
            self.assertEqual(bootstrap.existing_repository_name(self.repo), "sample")
        self.assertEqual(seen.get("GIT_CONFIG_KEY_0"), "safe.directory")

    def test_subdirectory_and_non_repository_keep_their_basename(self):
        nested = self.repo / "packages" / "web"
        nested.mkdir(parents=True)
        self.assertEqual(bootstrap.existing_repository_name(nested), "web")
        plain = self.root / "plain"
        plain.mkdir()
        self.assertEqual(bootstrap.existing_repository_name(plain), "plain")


class CommandLineTests(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(Path(bootstrap.__file__)), *args], capture_output=True, text=True
        )

    def test_empty_path_is_rejected_before_any_other_flow(self):
        for flag in ("--check", "--adopt"):
            result = self._run(flag, "", "--type", "simple", "--non-interactive", "--name", "x")
            self.assertEqual(result.returncode, 1)
            self.assertIn("non-empty PATH", result.stderr)

    def test_adopt_exits_nonzero_when_it_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "AGENTS.md").write_text("## Ours\n")  # not in git: refused
            result = self._run("--adopt", tmp, "--type", "simple")
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("refused  AGENTS.md", result.stdout)


if __name__ == "__main__":
    unittest.main()
