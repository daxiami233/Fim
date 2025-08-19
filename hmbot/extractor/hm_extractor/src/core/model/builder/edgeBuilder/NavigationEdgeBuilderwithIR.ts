import { Stmt, ArkMethod, Scene, ArkAssignStmt, ArkInvokeStmt, Cfg, Local, ArkInstanceInvokeExpr, AbstractExpr, StringType, ClassType, ArkNewExpr, UnknownType, PrinterBuilder, ArkFile } from "../../../../arkanalyzer/src";
import { PageTransitionGraph, PTGNode } from "../../PageTransitionGraph";
import { StringConstant } from "../../../../arkanalyzer/src/core/base/Constant";
import Const from "../../../common/Constant";
import Utils, { MyValue } from "../../../common/Utils";
import { EdgeBuilderInterface } from "./BasicEdgeBuilder";
import ValueAnalyzer from "../../../algorithm/ValueAnalyzer";


export class NavigationEdgeBuilderwithIR implements EdgeBuilderInterface{
    edgeBuilderStrategy: string = "NavigationEdgeBuilderwithIR";
    scene: Scene;
    ptg:PageTransitionGraph;

    constructor(scene: Scene, ptg: PageTransitionGraph){
        this.scene = scene;
        this.ptg = ptg;
    }

    identifyPTGEdge(ptgNode: PTGNode, method: ArkMethod): void {
        const cfg = method.getBody()?.getCfg();
        cfg!.buildDefUseChain();
        for(const unit of method.getCfg()!.getStmts()) {
            this.identifyPTGEdgeByIRAnalysis(ptgNode, unit, cfg!,  method);
        }
    }

    /**
     * 根据page迁移语句识别PTGEdge
     * 通过字节码分析
     * @param ptgNode 
     * @param unit 
     * @param cfg 
     * @param method 
     */
    identifyPTGEdgeByIRAnalysis(ptgNode: PTGNode, unit: Stmt, cfg: Cfg, method: ArkMethod) {
        // console.log("identify PTG edge by IR analysis");
        // 获取ptgNode所属的类名
        const caller = ptgNode.getClassOfPage().toString();
        let callee = "";
        // 判断unit是否为ArkInvokeStmt类型
        if (unit instanceof ArkInvokeStmt) {
            let expr = unit.getInvokeExpr();
            let invokeMethod = expr.getMethodSignature();
            const invokeMethodName = invokeMethod.getMethodSubSignature().getMethodName();
            // 判断调用表达式的方法名是否为pushUrl或replaceUrl
            for ( let entry of Const.NAVI_TRANSTION_STMTS.entries()){
                callee = "";
                if (entry[0] == invokeMethodName){

                    // 获取 pageTargetVar的对象（匿名类）名称
                    let pageTargetVarLoction = entry[1];
                    let pageTargetValue = expr.getArg(pageTargetVarLoction); 
                    let targetPageName = "";
                    if (pageTargetValue != undefined){
                        if (pageTargetValue instanceof Local){
                            //for local variable, get its concrete value first
                            if (entry[0] = 'pushPath') {
                                this.identifyPTGEdgeByNaviPathInfo(unit, method, pageTargetValue)
                            }
                            if (pageTargetValue.getType() instanceof StringType) {
                                pageTargetValue = Utils.getValueOfVar(method, pageTargetValue, new MyValue())?.value
                            } 
                        }
                        //获取目标页面类的名字
                        if (pageTargetValue instanceof StringConstant){
                            targetPageName  = (pageTargetValue as StringConstant).getValue();
                        }
                    }
                    for (let ptgNode of this.ptg.getPTGNodes()){
                        if (ptgNode.getPageAlias() == targetPageName){
                            callee = Utils.getComponentClassOfPage(this.scene, ptgNode.getModule(), ptgNode.getPagePath())!.getSignature().toString();
                        }
                    }
                    if (callee)
                        this.ptg.addPTGEdgeByName(caller, callee, unit);
                
                }

            }
        }
    }

    identifyPTGEdgeByNaviPathInfo(unit: Stmt, method: ArkMethod, value: Local) {
        let type = value.getType()
        if (type instanceof ClassType) {
            if (type.getClassSignature().getClassName() == 'NavPathInfo') {
                let stmt = value.getUsedStmts()[0];
                if ((stmt instanceof ArkAssignStmt) && 
                    (stmt.getRightOp() instanceof ArkInstanceInvokeExpr)) {
                    let invokeExpr = stmt.getRightOp() as ArkInstanceInvokeExpr;
                    let nameValue = invokeExpr.getArg(0);
                    const cfg = method.getBody()?.getCfg();
                    const chains = cfg?.getDefUseChains();
                    if (chains != undefined) {
                        let value = ValueAnalyzer.getValue(unit, chains, nameValue, this.scene);
                        console.log(value);
                    }
                }
            }
        }
    }
    
}